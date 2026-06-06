#include "bds_display.h"
#include "oled_spi.h"

#include <stdio.h>
#include <string.h>

/* OLED_WriteLine() 本身不会自动补齐一整行。
 * 这里统一把文本补成 21 个 ASCII 字符，确保旧内容被空格覆盖。
 * 128 像素宽度 / 每字符 6 像素约等于 21 个字符。
 */
static void BDS_Display_WriteLine(uint8_t row, const char *text)
{
  char line[22];
  size_t len;

  memset(line, ' ', 21);
  len = strlen(text);
  if (len > 21U)
  {
    len = 21U;
  }
  memcpy(line, text, len);
  line[21] = '\0';

  OLED_WriteLine(row, line);
}

void BDS_Display_Init(void)
{
  /* 显示层初始化包含两件事：
   * 1. 初始化底层 OLED；
   * 2. 显示开机默认界面，提示用户系统正在等待定位数据。
   */
  OLED_Init();
  BDS_Display_WriteLine(0U, "BDS WAITING");
  BDS_Display_WriteLine(1U, "TIME:--:--:--");
  BDS_Display_WriteLine(2U, "LAT:--");
  BDS_Display_WriteLine(3U, "LON:--");
  OLED_WriteAuthor(6U);
}

void BDS_Display_ShowParseError(void)
{
  /* 能进入这里说明已经收到一条疑似 RMC 的完整帧，但字段解析失败。
   * 这种情况通常来自串口干扰、半帧数据、波特率错误或模块输出格式异常。
   */
  BDS_Display_WriteLine(0U, "BDS PARSE ERR");
  BDS_Display_WriteLine(1U, "TIME:--:--:--");
  BDS_Display_WriteLine(2U, "LAT:--");
  BDS_Display_WriteLine(3U, "LON:--");
}

void BDS_Display_ShowFix(const BdsFix *fix)
{
  char line[22];

  if (fix == NULL)
  {
    return;
  }

  /* 即使尚未定位，RMC 语句通常仍会提供 UTC 时间。
   * 因此时间行总是先刷新，定位状态只影响经纬度是否显示。
   */
  BDS_NMEA_FormatBeijingTime(fix->utc, line, sizeof(line));
  BDS_Display_WriteLine(1U, line);

  if (fix->status[0] == 'A')
  {
    /* 状态 A 表示定位有效，可以显示转换后的十进制度数。 */
    BDS_Display_WriteLine(0U, "BDS FIX");
    BDS_NMEA_FormatCoordinate("LAT", fix->latitude, fix->ns, line, sizeof(line));
    BDS_Display_WriteLine(2U, line);
    BDS_NMEA_FormatCoordinate("LON", fix->longitude, fix->ew, line, sizeof(line));
    BDS_Display_WriteLine(3U, line);
  }
  else
  {
    /* 状态 V 或空状态表示未定位。此时隐藏无效经纬度，避免把 0000 或旧数据误认为定位结果。 */
    BDS_Display_WriteLine(0U, "BDS NO FIX");
    BDS_Display_WriteLine(2U, "LAT:--");
    BDS_Display_WriteLine(3U, "LON:--");
  }
}
