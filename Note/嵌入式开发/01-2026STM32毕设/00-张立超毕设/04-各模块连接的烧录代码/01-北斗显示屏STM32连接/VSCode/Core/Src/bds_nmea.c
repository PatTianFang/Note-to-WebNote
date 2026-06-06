#include "bds_nmea.h"

#include <stdio.h>
#include <string.h>

/* 捕获缓冲区：中断收到的字节先进入这里，直到遇到 '\n' 形成完整 NMEA 帧。 */
static char bds_capture_buffer[BDS_NMEA_FRAME_MAX];

/* 完整帧缓冲区：只保存被识别为 RMC 的最后一条完整帧，供主循环读取。 */
static char bds_frame_buffer[BDS_NMEA_FRAME_MAX];

/* 以下变量会在 UART 中断回调和主循环之间共享，因此用 volatile 防止编译器错误优化。 */
static volatile uint16_t bds_capture_len;
static volatile uint8_t bds_capture_active;
static volatile uint8_t bds_frame_ready;

/* 判断一条 NMEA 帧是否是 RMC 定位语句。
 * GPRMC：GPS talker
 * GNRMC：多星座 GNSS talker
 * BDRMC：北斗 talker
 */
static uint8_t BDS_NMEA_IsRmcFrame(const char *frame)
{
  return ((strncmp(frame, "$GPRMC,", 7U) == 0) || (strncmp(frame, "$GNRMC,", 7U) == 0) ||
          (strncmp(frame, "$BDRMC,", 7U) == 0)) ? 1U : 0U;
}

static uint8_t BDS_NMEA_CopyField(const char **cursor, char *dest, size_t dest_size)
{
  const char *start;
  const char *end;
  size_t len;

  if ((cursor == NULL) || (dest == NULL) || (dest_size == 0U))
  {
    return 0U;
  }

  /* NMEA 字段以逗号分隔，校验和前以 '*' 分隔。
   * 本函数从 cursor 当前字段开始复制，复制后把 cursor 移动到下一个字段。
   */
  start = *cursor;
  end = start;
  while ((*end != '\0') && (*end != ',') && (*end != '*') && (*end != '\r') && (*end != '\n'))
  {
    ++end;
  }

  len = (size_t)(end - start);
  if (len >= dest_size)
  {
    len = dest_size - 1U;
  }

  memcpy(dest, start, len);
  dest[len] = '\0';
  *cursor = (*end == ',') ? (end + 1) : end;

  return 1U;
}

static uint8_t BDS_NMEA_ParseCoordinateE6(const char *raw, uint32_t *degrees_e6)
{
  uint32_t integer_part = 0U;
  uint32_t fraction = 0U;
  uint32_t scale = 1U;
  uint32_t degrees;
  uint32_t minutes;
  uint32_t minutes_e6;
  const char *cursor = raw;

  if ((raw == NULL) || (raw[0] == '\0') || (degrees_e6 == NULL))
  {
    return 0U;
  }

  /* NMEA 坐标是 ddmm.mmmm 或 dddmm.mmmm。
   * 先把小数点前的部分读成整数：
   * 3000.1234 -> integer_part = 3000
   * 12030.0000 -> integer_part = 12030
   */
  while ((*cursor >= '0') && (*cursor <= '9'))
  {
    integer_part = (integer_part * 10U) + (uint32_t)(*cursor - '0');
    ++cursor;
  }

  /* 小数部分属于“分”的小数，不是“度”的小数。
   * 这里统一补齐到 6 位，得到“百万分之一分”。
   */
  if (*cursor == '.')
  {
    ++cursor;
    while ((*cursor >= '0') && (*cursor <= '9') && (scale < 1000000U))
    {
      fraction = (fraction * 10U) + (uint32_t)(*cursor - '0');
      scale *= 10U;
      ++cursor;
    }
  }

  while (scale < 1000000U)
  {
    fraction *= 10U;
    scale *= 10U;
  }

  /* 从 ddmm 或 dddmm 中拆出度和分：
   * 3000 -> 30 度 00 分
   * 12030 -> 120 度 30 分
   */
  degrees = integer_part / 100U;
  minutes = integer_part % 100U;
  if (minutes >= 60U)
  {
    return 0U;
  }

  /* 十进制度 = 度 + 分 / 60。
   * 为避免浮点 printf，内部用“百万分之一度”表示。
   */
  minutes_e6 = (minutes * 1000000U) + fraction;
  *degrees_e6 = (degrees * 1000000U) + ((minutes_e6 + 30U) / 60U);

  return 1U;
}

void BDS_NMEA_ResetCapture(void)
{
  /* 丢弃当前半帧，等待下一次 '$' 重新同步。 */
  bds_capture_len = 0U;
  bds_capture_active = 0U;
  bds_capture_buffer[0] = '\0';
}

void BDS_NMEA_PushByte(uint8_t byte)
{
  /* NMEA 帧以 '$' 开始。一旦看到 '$'，说明新帧开始，之前未完成的内容直接丢弃。 */
  if (byte == '$')
  {
    bds_capture_len = 0U;
    bds_capture_active = 1U;
  }

  if (bds_capture_active == 0U)
  {
    return;
  }

  if (bds_capture_len < (BDS_NMEA_FRAME_MAX - 1U))
  {
    bds_capture_buffer[bds_capture_len++] = (char)byte;
  }

  /* NMEA 标准以 CR/LF 结束。这里用 '\n' 判断帧结束，可以兼容 "\r\n"。 */
  if (byte == '\n')
  {
    bds_capture_buffer[bds_capture_len] = '\0';

    /* 只把 RMC 语句交给主循环；其它 GGA/GSV/VTG 等语句暂时忽略。 */
    if (BDS_NMEA_IsRmcFrame(bds_capture_buffer) != 0U)
    {
      size_t copy_len = bds_capture_len;
      if (copy_len >= BDS_NMEA_FRAME_MAX)
      {
        copy_len = BDS_NMEA_FRAME_MAX - 1U;
      }
      memcpy(bds_frame_buffer, bds_capture_buffer, copy_len);
      bds_frame_buffer[copy_len] = '\0';
      /* 数据内存屏障确保缓冲区内容先写完，再设置 ready 标志。 */
      __DMB();
      bds_frame_ready = 1U;
    }

    BDS_NMEA_ResetCapture();
  }
}

uint8_t BDS_NMEA_TakeFrame(char *frame, size_t frame_size)
{
  uint8_t ready = 0U;

  if ((frame == NULL) || (frame_size == 0U))
  {
    return 0U;
  }

  /* bds_frame_ready 和 bds_frame_buffer 会被中断回调更新。
   * 读取时临时关闭中断，避免主循环复制到一半时中断写入新帧。
   */
  __disable_irq();
  if (bds_frame_ready != 0U)
  {
    size_t len = strlen(bds_frame_buffer);
    if (len >= frame_size)
    {
      len = frame_size - 1U;
    }
    memcpy(frame, bds_frame_buffer, len);
    frame[len] = '\0';
    bds_frame_ready = 0U;
    ready = 1U;
  }
  __enable_irq();

  return ready;
}

uint8_t BDS_NMEA_ParseFrame(const char *frame, BdsFix *fix)
{
  const char *cursor;

  if ((frame == NULL) || (fix == NULL) || (BDS_NMEA_IsRmcFrame(frame) == 0U))
  {
    return 0U;
  }

  memset(fix, 0, sizeof(*fix));

  /* 第一个逗号之前是 talker+sentence，例如 "$GNRMC"。 */
  cursor = strchr(frame, ',');
  if (cursor == NULL)
  {
    return 0U;
  }
  ++cursor;

  /* RMC 字段顺序：
   * 1 UTC 时间
   * 2 状态 A/V
   * 3 纬度
   * 4 N/S
   * 5 经度
   * 6 E/W
   */
  if (BDS_NMEA_CopyField(&cursor, fix->utc, sizeof(fix->utc)) == 0U)
  {
    return 0U;
  }
  (void)BDS_NMEA_CopyField(&cursor, fix->status, sizeof(fix->status));
  (void)BDS_NMEA_CopyField(&cursor, fix->latitude, sizeof(fix->latitude));
  (void)BDS_NMEA_CopyField(&cursor, fix->ns, sizeof(fix->ns));
  (void)BDS_NMEA_CopyField(&cursor, fix->longitude, sizeof(fix->longitude));
  (void)BDS_NMEA_CopyField(&cursor, fix->ew, sizeof(fix->ew));

  return 1U;
}

void BDS_NMEA_FormatCoordinate(const char *label, const char *raw, const char *hemisphere, char *line, size_t line_size)
{
  uint32_t degrees_e6;
  char hemi;

  if ((line == NULL) || (line_size == 0U) || (label == NULL))
  {
    return;
  }

  /* 未定位时 RMC 可能给空坐标。此时显示 LAT:-- / LON:--。 */
  if ((BDS_NMEA_ParseCoordinateE6(raw, &degrees_e6) == 0U) || (hemisphere == NULL) || (hemisphere[0] == '\0'))
  {
    snprintf(line, line_size, "%s:--", label);
    return;
  }

  hemi = hemisphere[0];
  /* 将“百万分之一度”拆成整数部分和 6 位小数部分。 */
  snprintf(line, line_size, "%s:%lu.%06lu%c", label,
           (unsigned long)(degrees_e6 / 1000000U),
           (unsigned long)(degrees_e6 % 1000000U),
           hemi);
}

void BDS_NMEA_FormatBeijingTime(const char *utc, char *line, size_t line_size)
{
  uint8_t hour;
  uint8_t minute;
  uint8_t second;

  if ((line == NULL) || (line_size == 0U))
  {
    return;
  }

  /* RMC 时间是 UTC 的 hhmmss.sss。本项目只显示时分秒，不显示日期。 */
  if ((utc == NULL) || (strlen(utc) < 6U))
  {
    snprintf(line, line_size, "TIME:--:--:--");
    return;
  }

  for (uint8_t i = 0; i < 6U; ++i)
  {
    if ((utc[i] < '0') || (utc[i] > '9'))
    {
      snprintf(line, line_size, "TIME:--:--:--");
      return;
    }
  }

  hour = (uint8_t)(((utc[0] - '0') * 10) + (utc[1] - '0'));
  minute = (uint8_t)(((utc[2] - '0') * 10) + (utc[3] - '0'));
  second = (uint8_t)(((utc[4] - '0') * 10) + (utc[5] - '0'));

  if ((hour > 23U) || (minute > 59U) || (second > 59U))
  {
    snprintf(line, line_size, "TIME:--:--:--");
    return;
  }

  /* 北京时间 = UTC + 8。跨天时这里只回卷小时，不额外显示日期。 */
  hour = (uint8_t)((hour + 8U) % 24U);
  snprintf(line, line_size, "TIME:%02u:%02u:%02u", hour, minute, second);
}
