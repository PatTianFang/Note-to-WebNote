#ifndef __BDS_DISPLAY_H__
#define __BDS_DISPLAY_H__

#include "bds_nmea.h"

/* 初始化 OLED 并显示默认等待页面。 */
void BDS_Display_Init(void);

/* 显示解析错误页面。通常只有收到 RMC-like 数据但字段不符合预期时出现。 */
void BDS_Display_ShowParseError(void);

/* 根据一条 RMC 解析结果刷新状态、时间和经纬度显示。 */
void BDS_Display_ShowFix(const BdsFix *fix);

#endif
