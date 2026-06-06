#include "oled_spi.h"

#include <stddef.h>

/* 5x7 ASCII 字模以“列”为单位存储。
 * 每个字节代表一列的 8 个像素，bit0 是该列最上方像素。
 */
static const uint8_t OLED_GLYPH_SPACE[5] = {0x00, 0x00, 0x00, 0x00, 0x00};
static const uint8_t OLED_GLYPH_UNKNOWN[5] = {0x02, 0x01, 0x51, 0x09, 0x06};

/* “作者：张立超”的固定 16x16 中文点阵。
 * 每个汉字 32 字节：前 16 字节是上半部分 8 像素高，后 16 字节是下半部分。
 * OLED 的显存按 page 组织，每页 8 像素高，因此 16x16 汉字正好占两页。
 */
static const uint8_t OLED_AUTHOR_GLYPHS[6][32] = {
    {0x00, 0xC0, 0x30, 0xFC, 0x07, 0x21, 0x30, 0x1C, 0x0F, 0xF9, 0x48, 0x48, 0x48, 0x48, 0x08, 0x00,
     0x00, 0x00, 0x00, 0x7F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x00},
    {0x00, 0x20, 0x20, 0x24, 0x24, 0x24, 0xA4, 0xBF, 0x64, 0x24, 0x34, 0x38, 0x2C, 0x24, 0x20, 0x00,
     0x00, 0x04, 0x06, 0x02, 0x7F, 0x7F, 0x25, 0x25, 0x25, 0x25, 0x25, 0x25, 0x7F, 0x00, 0x00, 0x00},
    {0x00, 0x00, 0x00, 0x30, 0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
    {0x00, 0xE2, 0xE2, 0x22, 0x22, 0x3E, 0x40, 0x40, 0xFF, 0x40, 0xD0, 0x58, 0x46, 0x42, 0x40, 0x00,
     0x00, 0x01, 0x21, 0x21, 0x31, 0x1F, 0x00, 0x20, 0x3F, 0x30, 0x10, 0x07, 0x0C, 0x10, 0x30, 0x00},
    {0x00, 0x00, 0x08, 0x48, 0xC8, 0x08, 0x09, 0x0F, 0x08, 0x08, 0x08, 0xE8, 0x08, 0x08, 0x00, 0x00,
     0x00, 0x20, 0x20, 0x20, 0x21, 0x2F, 0x2C, 0x20, 0x20, 0x38, 0x2F, 0x21, 0x20, 0x20, 0x20, 0x00},
    {0x00, 0x20, 0x24, 0x24, 0xFF, 0xE4, 0x24, 0x20, 0x62, 0xB2, 0x8E, 0xA2, 0xA2, 0xBE, 0x06, 0x00,
     0x00, 0x38, 0x0F, 0x08, 0x1F, 0x3F, 0x21, 0x23, 0x20, 0x2F, 0x28, 0x28, 0x28, 0x2F, 0x20, 0x00},
};

static const uint8_t *OLED_GetGlyph(char ch)
{
  /* 只内置当前项目会用到的 ASCII 字符：大写字母、数字、冒号、小数点、减号和斜杠。
   * 小写字母会统一转成大写显示，减少字库体积。
   */
  static const uint8_t digits[10][5] = {
      {0x3E, 0x51, 0x49, 0x45, 0x3E},
      {0x00, 0x42, 0x7F, 0x40, 0x00},
      {0x42, 0x61, 0x51, 0x49, 0x46},
      {0x21, 0x41, 0x45, 0x4B, 0x31},
      {0x18, 0x14, 0x12, 0x7F, 0x10},
      {0x27, 0x45, 0x45, 0x45, 0x39},
      {0x3C, 0x4A, 0x49, 0x49, 0x30},
      {0x01, 0x71, 0x09, 0x05, 0x03},
      {0x36, 0x49, 0x49, 0x49, 0x36},
      {0x06, 0x49, 0x49, 0x29, 0x1E},
  };
  static const uint8_t letters[26][5] = {
      {0x7E, 0x11, 0x11, 0x11, 0x7E},
      {0x7F, 0x49, 0x49, 0x49, 0x36},
      {0x3E, 0x41, 0x41, 0x41, 0x22},
      {0x7F, 0x41, 0x41, 0x22, 0x1C},
      {0x7F, 0x49, 0x49, 0x49, 0x41},
      {0x7F, 0x09, 0x09, 0x09, 0x01},
      {0x3E, 0x41, 0x49, 0x49, 0x7A},
      {0x7F, 0x08, 0x08, 0x08, 0x7F},
      {0x00, 0x41, 0x7F, 0x41, 0x00},
      {0x20, 0x40, 0x41, 0x3F, 0x01},
      {0x7F, 0x08, 0x14, 0x22, 0x41},
      {0x7F, 0x40, 0x40, 0x40, 0x40},
      {0x7F, 0x02, 0x0C, 0x02, 0x7F},
      {0x7F, 0x04, 0x08, 0x10, 0x7F},
      {0x3E, 0x41, 0x41, 0x41, 0x3E},
      {0x7F, 0x09, 0x09, 0x09, 0x06},
      {0x3E, 0x41, 0x51, 0x21, 0x5E},
      {0x7F, 0x09, 0x19, 0x29, 0x46},
      {0x46, 0x49, 0x49, 0x49, 0x31},
      {0x01, 0x01, 0x7F, 0x01, 0x01},
      {0x3F, 0x40, 0x40, 0x40, 0x3F},
      {0x1F, 0x20, 0x40, 0x20, 0x1F},
      {0x3F, 0x40, 0x38, 0x40, 0x3F},
      {0x63, 0x14, 0x08, 0x14, 0x63},
      {0x07, 0x08, 0x70, 0x08, 0x07},
      {0x61, 0x51, 0x49, 0x45, 0x43},
  };
  static const uint8_t colon[5] = {0x00, 0x36, 0x36, 0x00, 0x00};
  static const uint8_t dot[5] = {0x00, 0x60, 0x60, 0x00, 0x00};
  static const uint8_t minus[5] = {0x08, 0x08, 0x08, 0x08, 0x08};
  static const uint8_t slash[5] = {0x20, 0x10, 0x08, 0x04, 0x02};

  if ((ch >= 'a') && (ch <= 'z'))
  {
    ch = (char)(ch - ('a' - 'A'));
  }
  if ((ch >= '0') && (ch <= '9'))
  {
    return digits[ch - '0'];
  }
  if ((ch >= 'A') && (ch <= 'Z'))
  {
    return letters[ch - 'A'];
  }
  if (ch == ':')
  {
    return colon;
  }
  if (ch == '.')
  {
    return dot;
  }
  if (ch == '-')
  {
    return minus;
  }
  if (ch == '/')
  {
    return slash;
  }
  if (ch == ' ')
  {
    return OLED_GLYPH_SPACE;
  }

  return OLED_GLYPH_UNKNOWN;
}

static void OLED_DelayShort(void)
{
  /* GPIO 模拟 SPI 的极短延时。
   * OLED 对时钟速度要求不高，插入少量 NOP 可以让 SCK/SDA 边沿更稳定。
   */
  for (volatile uint32_t i = 0; i < 20; ++i)
  {
    __NOP();
  }
}

static void OLED_WriteByte(uint8_t value)
{
  /* SPI 模式按高位先发。
   * 本 OLED 模块只需要单向写入，所以没有 MISO 读取逻辑。
   */
  for (uint8_t mask = 0x80U; mask != 0U; mask >>= 1)
  {
    /* 在 SCK 低电平期间准备 SDA 数据，再拉高 SCK 让 OLED 采样。 */
    HAL_GPIO_WritePin(OLED_SCK_GPIO_Port, OLED_SCK_Pin, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(OLED_SDA_GPIO_Port, OLED_SDA_Pin, (value & mask) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    OLED_DelayShort();
    HAL_GPIO_WritePin(OLED_SCK_GPIO_Port, OLED_SCK_Pin, GPIO_PIN_SET);
    OLED_DelayShort();
  }
  HAL_GPIO_WritePin(OLED_SCK_GPIO_Port, OLED_SCK_Pin, GPIO_PIN_RESET);
}

static void OLED_WriteCommand(uint8_t command)
{
  /* DC=0 表示当前字节是控制命令，例如设置页地址、开关显示等。 */
  HAL_GPIO_WritePin(OLED_DC_GPIO_Port, OLED_DC_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(OLED_CS_GPIO_Port, OLED_CS_Pin, GPIO_PIN_RESET);
  OLED_WriteByte(command);
  HAL_GPIO_WritePin(OLED_CS_GPIO_Port, OLED_CS_Pin, GPIO_PIN_SET);
}

static void OLED_WriteData(uint8_t data)
{
  /* DC=1 表示当前字节是显存数据，会直接影响 OLED 上的像素。 */
  HAL_GPIO_WritePin(OLED_DC_GPIO_Port, OLED_DC_Pin, GPIO_PIN_SET);
  HAL_GPIO_WritePin(OLED_CS_GPIO_Port, OLED_CS_Pin, GPIO_PIN_RESET);
  OLED_WriteByte(data);
  HAL_GPIO_WritePin(OLED_CS_GPIO_Port, OLED_CS_Pin, GPIO_PIN_SET);
}

static void OLED_SetPage(uint8_t page, uint8_t column)
{
  /* SSD1306 page 地址模式：
   * 0xB0~0xB7 选择第 0~7 页，每页高度 8 像素；
   * 低列地址和高列地址分别设置 0~127 的列位置。
   */
  OLED_WriteCommand((uint8_t)(0xB0U | (page & 0x07U)));
  OLED_WriteCommand((uint8_t)(0x00U | (column & 0x0FU)));
  OLED_WriteCommand((uint8_t)(0x10U | ((column >> 4) & 0x0FU)));
}

void OLED_Init(void)
{
  GPIO_InitTypeDef gpio = {0};

  /* OLED 使用 GPIOB8/B9/B12/B13，因此底层驱动自行打开 GPIOB 时钟并配置输出模式。 */
  __HAL_RCC_GPIOB_CLK_ENABLE();

  gpio.Pin = OLED_SCK_Pin | OLED_SDA_Pin | OLED_DC_Pin | OLED_CS_Pin;
  gpio.Mode = GPIO_MODE_OUTPUT_PP;
  gpio.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOB, &gpio);

  HAL_GPIO_WritePin(OLED_CS_GPIO_Port, OLED_CS_Pin, GPIO_PIN_SET);
  HAL_GPIO_WritePin(OLED_SCK_GPIO_Port, OLED_SCK_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(OLED_SDA_GPIO_Port, OLED_SDA_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(OLED_DC_GPIO_Port, OLED_DC_Pin, GPIO_PIN_RESET);

  /* RES 接在小系统板复位脚，软件不能单独拉复位。
   * 上电后等待一段时间，保证 OLED 控制器已经从硬件复位中稳定出来。
   */
  HAL_Delay(100);

  /* 以下为 SSD1306 常见初始化序列：
   * 关闭显示 -> 设置时钟/复用比/偏移/电荷泵/地址模式/扫描方向/对比度 -> 开启显示。
   */
  OLED_WriteCommand(0xAE);
  OLED_WriteCommand(0xD5);
  OLED_WriteCommand(0x80);
  OLED_WriteCommand(0xA8);
  OLED_WriteCommand(0x3F);
  OLED_WriteCommand(0xD3);
  OLED_WriteCommand(0x00);
  OLED_WriteCommand(0x40);
  OLED_WriteCommand(0x8D);
  OLED_WriteCommand(0x14);
  OLED_WriteCommand(0x20);
  OLED_WriteCommand(0x02);
  OLED_WriteCommand(0xA1);
  OLED_WriteCommand(0xC8);
  OLED_WriteCommand(0xDA);
  OLED_WriteCommand(0x12);
  OLED_WriteCommand(0x81);
  OLED_WriteCommand(0xCF);
  OLED_WriteCommand(0xD9);
  OLED_WriteCommand(0xF1);
  OLED_WriteCommand(0xDB);
  OLED_WriteCommand(0x40);
  OLED_WriteCommand(0xA4);
  OLED_WriteCommand(0xA6);
  OLED_WriteCommand(0xAF);

  OLED_Clear();
}

void OLED_Clear(void)
{
  /* 全屏清零：8 页 * 128 列。每写 1 字节清掉当前列的 8 个垂直像素。 */
  for (uint8_t page = 0; page < 8U; ++page)
  {
    OLED_SetPage(page, 0U);
    for (uint8_t column = 0; column < 128U; ++column)
    {
      OLED_WriteData(0x00);
    }
  }
}

void OLED_WriteLine(uint8_t row, const char *text)
{
  uint8_t column = 0U;

  if (row > 7U)
  {
    return;
  }

  /* 写新行前先清空该页，避免短字符串覆盖长字符串时残留旧字符。 */
  OLED_SetPage(row, 0U);
  for (uint8_t i = 0; i < 128U; ++i)
  {
    OLED_WriteData(0x00);
  }

  /* 每个 ASCII 字符占 5 列，后面补 1 列空白，形成 6 像素宽字符。 */
  OLED_SetPage(row, 0U);
  while ((text != NULL) && (*text != '\0') && (column <= 122U))
  {
    const uint8_t *glyph = OLED_GetGlyph(*text++);
    for (uint8_t i = 0; i < 5U; ++i)
    {
      OLED_WriteData(glyph[i]);
      ++column;
    }
    OLED_WriteData(0x00);
    ++column;
  }
}

void OLED_WriteAuthor(uint8_t row)
{
  if (row > 6U)
  {
    return;
  }

  /* 作者字样是 16 像素高，需要连续清空两页再写入。 */
  for (uint8_t page_offset = 0; page_offset < 2U; ++page_offset)
  {
    OLED_SetPage((uint8_t)(row + page_offset), 0U);
    for (uint8_t column = 0; column < 128U; ++column)
    {
      OLED_WriteData(0x00);
    }
  }

  /* 先写所有汉字的上半部分。 */
  OLED_SetPage(row, 0U);
  for (uint8_t glyph = 0; glyph < 6U; ++glyph)
  {
    for (uint8_t column = 0; column < 16U; ++column)
    {
      OLED_WriteData(OLED_AUTHOR_GLYPHS[glyph][column]);
    }
  }

  /* 再写所有汉字的下半部分。上下两页组合后形成完整中文。 */
  OLED_SetPage((uint8_t)(row + 1U), 0U);
  for (uint8_t glyph = 0; glyph < 6U; ++glyph)
  {
    for (uint8_t column = 0; column < 16U; ++column)
    {
      OLED_WriteData(OLED_AUTHOR_GLYPHS[glyph][16U + column]);
    }
  }
}
