#ifndef __BDS_NMEA_H__
#define __BDS_NMEA_H__

#include "stm32f1xx_hal.h"
#include <stddef.h>
#include <stdint.h>

/* 单条 NMEA 帧缓存长度。
 * RMC 语句通常不足 90 字节，这里留 96 字节用于包含起始 '$'、结尾 CR/LF 和字符串结束符。
 */
#define BDS_NMEA_FRAME_MAX 96U

/* 从 RMC 语句中提取出的最小定位信息。
 * 字段保持为字符串，原因是：
 * 1. RMC 原始字段本身就是 ASCII；
 * 2. 显示层需要按需格式化；
 * 3. 避免在中断或解析阶段引入浮点计算。
 */
typedef struct
{
  char utc[11];       /* UTC 时间，格式通常为 hhmmss.sss。 */
  char status[2];    /* 定位状态：A 表示有效，V 表示无效。 */
  char latitude[11]; /* 纬度原始字段，NMEA 格式为 ddmm.mmmm。 */
  char ns[2];        /* N/S，北纬或南纬。 */
  char longitude[12];/* 经度原始字段，NMEA 格式为 dddmm.mmmm。 */
  char ew[2];        /* E/W，东经或西经。 */
} BdsFix;

/* 重置串口字节流捕获状态。通常在启动和串口错误后调用。 */
void BDS_NMEA_ResetCapture(void);

/* 将 USART 中断收到的一个字节送入 NMEA 捕获器。
 * 该函数设计为可在 UART 接收完成回调中调用，因此内部只做轻量级缓存和帧完成标记。
 */
void BDS_NMEA_PushByte(uint8_t byte);

/* 从捕获器中取出一条完整 RMC 帧。
 * 返回 1 表示取到了新帧，返回 0 表示暂无新帧。
 */
uint8_t BDS_NMEA_TakeFrame(char *frame, size_t frame_size);

/* 解析 RMC 帧，提取时间、定位状态、经纬度和方向字段。 */
uint8_t BDS_NMEA_ParseFrame(const char *frame, BdsFix *fix);

/* 将 NMEA 度分格式坐标转换为十进制度数字符串，例如 LAT:30.123456N。 */
void BDS_NMEA_FormatCoordinate(const char *label, const char *raw, const char *hemisphere, char *line, size_t line_size);

/* 将 RMC UTC 时间转换为北京时间字符串，例如 TIME:14:30:05。 */
void BDS_NMEA_FormatBeijingTime(const char *utc, char *line, size_t line_size);

#endif
