# RQSDK 快速上手 (Ricequant SDK Manual)

参考网页: https://www.ricequant.com/doc/rqsdk/manual-rqsdk

## 安装 Ricequant SDK

### 1. 安装 Python 环境
Ricequant SDK 需要 64-bit，Python3.6+运行环境。支持 Linux, Windows, Mac 等平台。建议使用 Anaconda 进行环境配置。

### 2. 安装 rqsdk
在激活的虚拟环境中，执行如下命令：
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple rqsdk
```
安装成功后，终端输入 `rqsdk` 即可看到命令提示。

### 3. 配置代理 (可选)
如果环境需要代理，运行：
```bash
rqsdk proxy
```
交互式配置，完成后通过 `rqsdk proxy info` 检查。

### 4. 配置许可证信息 (License)
使用米筐发放的 License。运行以下命令交互式输入：
```bash
rqsdk license
```
或查看当前配置:
```bash
rqsdk license info
```

### 5. 安装产品 (包含 rqdatac)
目前 Ricequant SDK 包含的可选产品如下：
- **rqdatac** (默认依赖): 金融数据 API
- **rqoptimizer**: 股票组合优化器
- **rqfactor**: 因子投研工具
- **rqalpha_plus**: 回测引擎

安装命令示例：
```bash
rqsdk install rqdatac
```
*(如果需要回测功能可安装 `rqalpha_plus`)*

### 6. 更新 SDK 版本
```bash
rqsdk update
```

## 数据初始化与下载 (RQData)
RQAlpha Plus 回测依赖历史行情数据缓存。

**针对试用客户（重要）：**
试用客户建议使用 `--sample` 不消耗流量下载基础数据：
```bash
rqsdk download-data --sample
```

若需增量更新数据，可以执行：
```bash
rqsdk update-data --base --minbar 000001.XSHE
```
*(注：如果下载全量数据可能消耗约1GB流量，请确认流量额度)*

## 代码中初始化 RQData
安装完成后，在 Python 代码中初始化可以参考：
```python
import rqdatac
# 方式1：如果你已通过 rqsdk license 配置了凭证，直接调用 init()
rqdatac.init()

# 方式2：使用用户名密码初始化
rqdatac.init("username", "password")
```
在 `.env` 中可配置相关变量供代码加载。
