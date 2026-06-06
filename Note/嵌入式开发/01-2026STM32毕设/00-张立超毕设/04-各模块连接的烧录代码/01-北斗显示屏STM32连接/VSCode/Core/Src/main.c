/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "bds_display.h"
#include "bds_nmea.h"

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
/* UART2 每次中断接收 1 个字节。
 * 接收完成后在 HAL_UART_RxCpltCallback() 中把该字节交给 BDS_NMEA_PushByte()，
 * 然后立即重新启动下一字节接收。
 */
static uint8_t bds_rx_byte;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
/* USER CODE BEGIN PFP */
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* 主循环临时变量：
   * frame 保存从中断侧捕获到的一整条 RMC 语句；
   * fix 保存解析后的时间、状态和经纬度字段。
   */
  char frame[BDS_NMEA_FRAME_MAX];
  BdsFix fix;

  /* HAL_Init() 会初始化 SysTick 和 HAL 内部状态。
   * SystemClock_Config() 当前使用 HSI 8MHz，无 PLL。
   */
  HAL_Init();
  SystemClock_Config();

  /* GPIOA/USART2 是 GPS 模块通信所需硬件。
   * OLED 的 GPIOB 引脚由 OLED_Init() 自己初始化，保持显示驱动自包含。
   */
  MX_GPIO_Init();
  MX_USART2_UART_Init();

  /* 初始化显示层：OLED 初始化、默认等待页、作者字样。 */
  BDS_Display_Init();

  /* 初始化 NMEA 捕获状态并启动 USART2 单字节中断接收。 */
  BDS_NMEA_ResetCapture();
  HAL_UART_Receive_IT(&huart2, &bds_rx_byte, 1);

  while (1)
  {
    /* 中断里只负责接收字节和拼帧；主循环负责解析和刷新显示。
     * 这样可以避免在中断中做字符串处理或 OLED 刷新，降低丢字节风险。
     */
    if (BDS_NMEA_TakeFrame(frame, sizeof(frame)) != 0U)
    {
      if (BDS_NMEA_ParseFrame(frame, &fix) != 0U)
      {
        BDS_Display_ShowFix(&fix);
      }
      else
      {
        BDS_Display_ShowParseError();
      }
    }
  }
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                              | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{
  /* GPS/北斗模块文档要求使用 9600 8N1。
   * PA2 = USART2_TX，PA3 = USART2_RX，具体 GPIO 初始化在 stm32f1xx_hal_msp.c。
   */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 9600;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* 这里保留 GPIOA 时钟使能，USART2 的 PA2/PA3 由 HAL_UART_MspInit() 进一步配置。
   * OLED 使用 GPIOB，由 oled_spi.c 中的 OLED_Init() 独立配置。
   */
  __HAL_RCC_GPIOA_CLK_ENABLE();
}

/* USER CODE BEGIN 4 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if ((huart != NULL) && (huart->Instance == USART2))
  {
    /* 收到 1 字节后立刻交给 NMEA 捕获器。
     * 捕获器只做轻量处理：寻找 '$' 开始符、缓存到 '\n'、标记完整帧。
     */
    BDS_NMEA_PushByte(bds_rx_byte);

    /* 必须重新启动下一次中断接收，否则 HAL 只会收这一个字节。 */
    (void)HAL_UART_Receive_IT(&huart2, &bds_rx_byte, 1);
  }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
  if ((huart != NULL) && (huart->Instance == USART2))
  {
    /* 串口错误可能导致当前半帧数据不完整，直接丢弃并重新同步到下一条 '$'。 */
    BDS_NMEA_ResetCapture();
    (void)HAL_UART_Receive_IT(&huart2, &bds_rx_byte, 1);
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  __disable_irq();
  while (1)
  {
  }
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  (void)file;
  (void)line;
}
#endif
