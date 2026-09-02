# 项目专用 ClipProxy 链式中转

## 目标

- 让 chat2api 的出站请求最终使用 ClipProxy 固定 ISP IP。
- 不修改 Windows 系统代理、TUN 或用户现有 Clash 订阅。
- 迁移到另一台电脑时只需重新填写 ClipProxy 凭据和启动可用的本机 Clash。

## 实现范围

- 启动器按常见端口发现本机 Clash HTTP 入口。
- 生成被 Git 忽略的 `.runtime/proxy-bridge.yaml`，使用 Mihomo `dialer-proxy` 将 ClipProxy 链到本机 Clash。
- 项目专用 Mihomo 监听 `127.0.0.1:7896`，仅通过网关子进程环境变量注入。
- 工作台出口测试使用同一链路，测试结束停止临时中转进程。

## 非目标与回滚

- 不自动开启或改写 VPN/TUN，不修改主 Clash 配置，不把代理凭据写入日志或提交内容。
- 清除 `PROXY_URL` 并重启即可恢复直连；删除 `.runtime/` 仅移除生成的运行时配置。

## 验收

- 配置生成测试覆盖 SOCKS5/HTTP、凭据解码、链式节点和全量规则。
- 当前电脑真实启动中转并探测出口为 `38.248.239.46`。
