# Cliproxy、VPN 与 Clash/Mihomo 路由研究

- 研究日期：2026-09-01
- 问题：Cliproxy 官方是否要求/建议开 VPN；固定静态 ISP 代理与 Clash 系统代理/TUN 的关系；VPN+代理叠加对延迟和连通性的影响。
- 证据顺序：Cliproxy 官方帮助中心/官网 > Mihomo 官方文档与 GitHub issue（可复现的社区报告）> 论坛搜索摘要。

## 结论摘要

1. **没有官方 VPN 要求或建议的证据。** Cliproxy 帮助中心的完整索引和页面正文没有“需开启 VPN/VPN 开关”的说明；`llms-full.txt` 中唯一 VPN 字符串命中来自图片文件名。应表述为“官方文档未要求/建议 VPN”，而不是“VPN 一定不能用”。
2. **大陆使用是官方不支持场景。** 官网中文页声明“由于政策原因，本站代理服务不支持在中国大陆使用”。该声明没有把 VPN 作为解决方案，不能推断“开 VPN 即获官方支持”。
3. **静态 ISP 是 Cliproxy 的出口代理凭据，不是本机 VPN。** 静态 IP 购买/提取后通过服务器 IP+端口连接；可选用户名/密码，或把当前网络 IP 加入白名单后免认证。Clash 的“系统代理”只是让应用把 HTTP/SOCKS 请求发给本机监听端口；Mihomo TUN 则创建虚拟网卡并改写路由，把更广泛的 IP 流量导入核心。两者都可把 Cliproxy 静态 SOCKS5 作为出站节点，但 TUN 并不等于 VPN 服务。
4. **VPN 与代理叠加会增加一跳和状态复杂度，结果取决于拓扑。** Mihomo 官方文档说明 TUN `auto-route` 会把全局流量送入 TUN；GitHub issue #957 的实测报告显示 TUN 捕获外部 SOCKS5（本机 Xray）时出现疑似无限循环、连接关闭错误，说明错误的回环/路由排除会导致不可达，而非提升稳定性。叠加 VPN 还会增加握手、加密和路径 RTT；只有当 VPN 解决了到 Cliproxy 中间服务器的可达性或路径质量时，才可能抵消额外开销。应逐层测量直连、VPN、代理、VPN+代理四种路径。

## 官方 Cliproxy 证据

### VPN：未找到要求或建议

- [Cliproxy 帮助中心完整索引（llms.txt）](https://help.cliproxy.com/llms.txt) 列出全部英文/中文页面；无 VPN 配置或“需开启 VPN”条目。
- [Cliproxy 帮助中心 Overview](https://help.cliproxy.com/overview.md) 的快速使用、静态 IP、浏览器和 FAQ 链接中没有 VPN 步骤。
- [Cliproxy 官网中文页](https://cliproxy.com/zh/)：页脚声明“由于政策原因，本站代理服务不支持在中国大陆使用”。这是地域服务政策，不是 VPN 建议。

### 静态 ISP 的连接方式

- [静态 IP 代理说明](https://help.cliproxy.com/zh/static.md)：静态 IP“固定不变”“稳定性”高，通常由 ISP/管理员提供或配置；它描述的是代理 IP 属性，不是 VPN 隧道。
- [提取并使用静态长效 ISP](https://help.cliproxy.com/zh/static/used.md)：购买后使用记录提供连接所需用户名/密码；白名单模式下，当前网络 IP 在白名单时“无需配置用户名或密码”，只需配置静态 IP 的 IP 和端口。
- [白名单模式](https://help.cliproxy.com/zh/static/whitelist.md)：通过已添加白名单 IP 连接静态 IP，“无需进行用户名和密码的校验”，只配置 IP 和端口即可。
- [Cliproxy 支持的代理协议](https://help.cliproxy.com/faq/cliproxy-faq8.md)：支持 HTTP/HTTPS 与 SOCKS5；SOCKS5 用于更广泛的 TCP/UDP 应用。Clash 出站应按实际协议配置。
- [代理有效性验证](https://help.cliproxy.com/faq/cliproxy-faq1.md)：官方示例使用 `curl --proxy socks5://username:password@Hostname:Port https://mayips.com`；403/407 通常表示认证失败，超时表示不可达或配置错误。

### 流量套餐的中间服务器

- [流量套餐快速集成](https://help.cliproxy.com/faq/traffic-api.md)：客户端连接 Socks5 中间服务器；目前提供 `us.cliproxy.io`、`sg.cliproxy.io`，建议选择更接近出口 IP 地区的中间服务器。账号中的 `username` 与 `region` 必填，密码只用于认证；认证失败会拒绝连接。该“中间服务器→出口 IP”逻辑与静态 ISP 的固定 IP 模式不同。
- [Chrome 使用 Cliproxy](https://help.cliproxy.com/browser1/google.md)：可通过 Chrome 启动参数或 Windows 系统代理设置 SOCKS5；但 Chrome 不能直接设置账号密码，官方注明这些步骤仅适用于静态 IP 白名单模式，流量套餐需扩展程序。

## Clash/Mihomo 的系统代理与 TUN 关系

- [Mihomo TUN 官方文档（英文）](https://wiki.metacubex.one/en/config/inbound/tun/)：`auto-route`“自动设置全局路由”，将全局流量路由进入 TUN 网卡；`strict-route` 在启用 auto-route 时强制所有连接走 TUN，并用于防止地址泄漏/DNS 绕过；`dns-hijack` 将匹配的 DNS 请求导入内部 DNS 模块。TUN 是内核路由/虚拟网卡层的流量捕获机制。
- 同页说明协议栈：`system` 使用系统协议栈，体验更稳定且资源占用较低；`mixed` 为 TCP system、UDP gvisor 的混合；并提醒防火墙可能阻断 system/mixed。该页没有要求另开商业 VPN。
- Cliproxy 的 [Chrome 系统代理步骤](https://help.cliproxy.com/browser1/google.md) 属于应用/系统代理设置，作用范围取决于遵循系统代理的应用；它与 Mihomo TUN 的全局路由不是同一层。实践上应选择一条入口，避免让 TUN 捕获 Mihomo 自己连接到 Cliproxy 的流量，形成回环。

## 社区/工程经验：叠加的连通性与延迟风险

- [MetaCubeX/mihomo issue #957：How to use TUN mode with an external SOCKS5 proxy?](https://github.com/MetaCubeX/mihomo/issues/957)（2024-01-03，公开复现报告）：用户让 Mihomo TUN（`auto-route: true`）把流量送到本机 Xray SOCKS5；SOCKS5 单独工作，但启用 TUN 后“doesn't work”，疑似无限循环，Xray 报 `failed to transport all TCP response`、`context canceled`。这是 VPN/代理分层或回环排除错误会导致连接失败的直接案例，不代表所有配置必然失败。
- [MetaCubeX/mihomo issue #1588：Mihomo → WARP proxy mode 出现 EOF](https://github.com/MetaCubeX/mihomo/issues/1588)（2024-10-14）：服务端把 Mihomo 出站再转到 Cloudflare WARP 的本地 SOCKS5/Proxy mode；日志持续出现对目标站点的 `error: EOF`。该报告显示“代理核心再叠加另一 VPN/代理层”会引入额外兼容性故障，需要逐层验证，不能假设叠加后更稳定。
- [LINUX DO：clash 链式代理教程，以及避坑 clipProxy](https://linux.do/t/topic/1880689)（论坛搜索可见摘要，正文受访问限制）：发帖者称购买 ClipProxy 试用后“非常辣鸡”，并讨论 Clash 链式代理。该条只能作为个体体验，不能当作性能统计或官方结论。

### 对延迟的工程性判断（需实测）

- VPN+Cliproxy 至少包含“本机→VPN 网关→Cliproxy 接入/中间服务器→目标站点”多段路径；每增加一段通常增加 RTT、加密/解密 CPU 和连接建立时间，吞吐还受最慢链路限制。这是网络拓扑推论，不是 Cliproxy SLA。
- 若直连到 Cliproxy 接入点被阻断或路由很差，VPN 可能改善**可达性**，但不保证更低延迟；VPN 出口位置与 Cliproxy 中间服务器/静态 ISP 出口的地理距离决定收益或损失。
- 建议用同一目标和多次样本记录 DNS、TCP/TLS 建连、首字节和总耗时，并确认出口 IP：A 直连+Cliproxy、B VPN+Cliproxy、C 仅 VPN、D 直连。出现超时/EOF/连接回环时，先关闭 TUN 或系统代理中的一层，确认单层链路，再逐层加入并设置路由排除。

## 实施建议（面向本项目）

1. 默认先使用 Cliproxy 静态 ISP 的 SOCKS5/HTTP 出站，在 Clash 中通过**系统代理**验证；静态白名单模式只需 IP+端口，账密模式需安全保存凭据。
2. 只有需要覆盖不遵循系统代理的程序时才启用 Mihomo TUN；将 Cliproxy 服务器地址、VPN 网关和本地控制端口加入 TUN 排除/直连规则，防止核心自捕获回环。
3. 不把“官网大陆不支持”解释为“官方建议开 VPN”；合规与可用性应由用户确认。任何 VPN+代理组合先做单层连通性和延迟基线，再决定是否长期启用。
