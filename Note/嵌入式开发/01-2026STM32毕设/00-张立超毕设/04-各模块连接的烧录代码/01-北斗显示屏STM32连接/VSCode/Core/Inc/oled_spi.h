#ifndef __OLED_SPI_H__
#define __OLED_SPI_H__

#include "stm32f1xx_hal.h"
#include <stdint.h>

/* OLED 使用 4 线 SPI 接口，但这里用 GPIO 模拟 SPI。
 * 接线来自实验文档：
 * PB8  -> D0/SCK
 * PB9  -> D1/SDA
 * PB12 -> DC
 * PB13 -> CS
 * RES  -> 小系统板 R/RESET
 */
#define OLED_SCK_GPIO_Port GPIOB
#define OLED_SCK_Pin GPIO_PIN_8

#define OLED_SDA_GPIO_Port GPIOB
#define OLED_SDA_Pin GPIO_PIN_9

#define OLED_DC_GPIO_Port GPIOB
#define OLED_DC_Pin GPIO_PIN_12

#define OLED_CS_GPIO_Port GPIOB
#define OLED_CS_Pin GPIO_PIN_13

/* 初始化 GPIO 和 SSD1306 类 OLED 控制器。 */
void OLED_Init(void);

/* 清空整屏 128x64 像素。 */
void OLED_Clear(void);

/* 使用 5x7 ASCII 字模写一行英文/数字文本，row 范围为 0~7。 */
void OLED_WriteLine(uint8_t row, const char *text);

/* 使用固定 16x16 中文点阵显示“作者：张立超”，row 是起始页，建议为 6。 */
void OLED_WriteAuthor(uint8_t row);

#endif
