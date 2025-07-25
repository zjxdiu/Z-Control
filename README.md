## 简介

Z-Control是一个基于python的简单Windows PC远程监控和控制软件。

**声明：部分代码由AI生成或经AI辅助编写。**

## 核心功能

- 检查客户端在线情况。
- 获取客户端屏幕截图（单次/按秒自动）。
- 获取客户端进程列表（按进程名排序）。
- 远程发送定时关机/取消命令。
- 客户端列表管理（保存到服务端）。

## 设计特性

- 使用Flask构建的http交互。
- 网页界面、服务端和客户端三端分离，便于远程控制操作。
- 简易的api key认证机制。
- Web界面访问IP控制。
- 客户端日志记录（该功能正计划进行大幅修改）。

## 使用方法

适用系统：客户端推荐Windows 10及以上，但理论上在有合适的外部环境时也可用于Linux和MacOS。服务端无限制，确保python3及相关依赖正常安装即可。

1. 前置准备：
	- python3（服务端必须，客户端按需）
	- 在服务端环境上：`pip install flask requests waitress`
	- 在客户端环境上：`pip install Flask Pillow psutil waitress` （若使用编译后的exe版本则无需）
	- 填写[配置文件](https://github.com/zjxdiu/Z-Control#%E9%85%8D%E7%BD%AE%E6%96%87%E4%BB%B6)

2. 部署服务端：
	- 下载或git clone本仓库后进入server文件夹。
	- 启动服务端：`python server.py`

3. 部署客户端：
	- **以下方式部署的是后台静默运行的编译版，仅适用于Windows**
	- 从 [releases](https://github.com/zjxdiu/Z-Control/releases) 中下载client-dist-xxx.zip
	- 解压后运行其中的client.exe即可。
	
4. 部署客户端（从代码运行）：
	- **以下方式是从py文件直接运行**
	- 下载或git clone本仓库后进入client文件夹。
	- 启动客户端：`python client.py`
	
## 配置文件

客户端和服务端的目录下均应有config.ini，该文件存储了程序运行必要的配置。

客户端配置：
- port：监听的端口，用于提供给服务端连接。
- api_key：简易认证机制，防止一些伪造的http请求控制客户端。

服务端配置：
- port：从这个端口开放web界面。
- allowed_ips：允许哪些IP访问web界面。

安全说明：由于只做了普通的api key认证且没有https加密连接，因此阻止恶意设备访问web界面是非常重要的；建议配合zerotier等安全组网方式使用。

注意：web界面添加客户端时需与客户端本地配置文件中的api_key一致，否则无法连接。

## TO-DO

因为我知道自己可能懒得更新了，这里就不写任务列表了，只留一些优化方向吧。
- 加入一种特殊的配置，以允许任意IP访问web界面
- 实现https加密连接
- 优化截图方式以提高性能
- 客户端日志文件自动清理

## 开发

因为我做这个项目的目的主要是为了满足自己的需求（即远程监控和控制PC）以及练习python编程，目前的版本已经足以满足我的使用，因此可能后续不会再更新。
