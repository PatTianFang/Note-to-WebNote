import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter
from glob import glob
import os

# ── 字体定义 ──
zh_font = FontProperties(fname='C:/Windows/Fonts/simsun.ttc', size=10)

# ── SCI 风格全局设置 ──
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'axes.unicode_minus': False,
    'font.size': 11,
    'axes.linewidth': 1.0,
    'axes.labelsize': 10,
    'axes.titlesize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.major.width': 1.0,
    'ytick.major.width': 1.0,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.size': 5,
    'ytick.major.size': 5,
    'legend.fontsize': 9,
    'legend.frameon': True,
    'legend.edgecolor': '0.8',
    'legend.fancybox': False,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
    'mathtext.fontset': 'stix',
})

# ── 自动扫描当前目录下所有 seed*.csv 文件 ──
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_files = sorted(glob(os.path.join(script_dir, 'seed*.csv')))

if not csv_files:
    raise FileNotFoundError(f"未在 {script_dir} 中找到任何 seed*.csv 文件")

print(f"找到 {len(csv_files)} 个 CSV 文件: {[os.path.basename(f) for f in csv_files]}")

# 读取所有 CSV 文件
all_data = [np.genfromtxt(f, delimiter=',', skip_header=1) for f in csv_files]

# 取所有文件最大Step中的最小值作为横坐标上限
x_max = min(d[:, 1].max() for d in all_data)

# 按Step范围截取各文件
all_data = [d[d[:, 1] <= x_max] for d in all_data]

# 取最小行数对齐
n = min(len(d) for d in all_data)
all_data = [d[:n] for d in all_data]

steps = all_data[0][:, 1]
all_values = [d[:, 2] for d in all_data]

# 计算最大值、最小值、最大最小值的均值
upper = np.maximum.reduce(all_values)
lower = np.minimum.reduce(all_values)
mid = (upper + lower) / 2

# 绘图
fig, ax = plt.subplots(figsize=(3.5, 2.3))

ax.fill_between(steps, lower, upper, alpha=0.6, color='#acd9fd', label='最大–最小范围', linewidth=0)
ax.plot(steps, mid, color='#37a0f3', linewidth=1.0, label='均值', linestyle='-')

# 坐标轴刻度朝内（无次刻度）
ax.tick_params(axis='x', which='major', direction='in')
ax.tick_params(axis='y', which='major', direction='in')

# 上、右边框刻度标签隐藏（SCI 常见样式）
ax.tick_params(which='both', top=False, right=False, labeltop=False, labelright=False)

# 横轴标签：中文宋体，×10⁷ 通过 mathtext 用 Times New Roman
ax.set_xlabel(r'训练步数（$\times 10^{7}$）', fontproperties=zh_font)
ax.set_ylabel('回合平均奖励', fontproperties=zh_font)

# 图例
leg = ax.legend(loc='lower right', bbox_to_anchor=(0.98, 0.05),
                handlelength=1.5, handletextpad=0.4, borderpad=0.3, prop=zh_font)

# 横轴以 10^7 为单位显示，无小数
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x/1e7:.0f}'))

# 网格（淡色虚线）
ax.grid(True, which='major', linestyle='--', linewidth=0.4, alpha=0.5)

# 边框四边保留
for spine in ax.spines.values():
    spine.set_linewidth(1.0)
    spine.set_color('0.0')

plt.tight_layout()
plt.savefig('plot_csv.png')
plt.savefig('plot_csv.pdf')
plt.show()
