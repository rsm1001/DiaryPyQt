# 部署与运维

日记后端与 `Nexus-Blade` 金融系统隔离，只复用已验证的 Tailscale/SSH 连接方式。服务器只用于运行、发布、备份与回滚，不能直接开发。

## 每次部署前：先验证连接

1. 优先通过已配置的 Tailscale/SSH 别名建立连接。若出现 Tailscale SSH 额外身份验证提示，先访问**本次连接提示的动态验证链接**完成验证，再重新确认连接；不要复用旧链接，也不要将链接写入文档、日志或仓库。
2. 连接成功后，只读检查登录用户、主机名、`diary-server.service` 状态和磁盘空间；确认目标是日记服务器。先把下例中的 `$sshAlias` 替换为本机已验证的 SSH 别名：

   ```powershell
   $sshAlias = '<已验证的 SSH 别名>'
   ssh -o BatchMode=yes -o StrictHostKeyChecking=yes $sshAlias 'id -un; hostname; systemctl is-active diary-server.service; df -h /'
   ```

3. 连接未通过、目标不符或空间不足时停止，不执行备份、上传或部署。服务未运行时先确认属于首次部署还是故障；原因不明时暂停部署。
4. 连接验证不等于发布授权：还须完成本地测试、构建并得到用户明确确认，才能在服务器开展部署。

## 文件说明

- `diary-server.service`：独立的 systemd 服务。
- `nginx-diary.conf.template`：HTTPS 反向代理模板，域名从 `${DIARY_DOMAIN}` 配置。
- `backend.env.example`：环境配置示例，不含真实密钥。
- `install.sh`：创建独立的程序、虚拟环境和数据目录，安装日记服务模板。
- `backup.sh`：备份日记数据库与音频，清理超过 30 天的备份。

## 发布顺序

1. 按上方步骤验证连接、目标身份、日记服务状态和磁盘空间。
2. 在 Windows 本地完成测试与构建，取得用户明确发布确认。
3. 备份 `/var/lib/diary-server`，仅部署到 `/opt/diary-server/app`。
4. 配置 `/etc/diary-server/backend.env`，只启动或重启 `diary-server.service`。
5. 确认日记后端健康检查及对外 HTTPS 访问；失败时只回滚日记系统，不操作金融系统。

不得读取、输出、提交或复制真实环境文件、密钥、密码或 Token。

## 当前服务器入口（2026-09-26）

服务运行于独立的 `/opt/diary-server/app`、`/var/lib/diary-server`、`diary-server.service`，监听 `127.0.0.1:8010`。额外的 Nginx 站点 `diary-tailnet` **仅监听** Tailscale IP `100.125.111.63:8020` 并代理 8010；未修改金融站点。客户端须先登录同一 Tailnet，使用 `http://100.125.111.63:8020`。Tailnet 隧道加密，但内层为 HTTP，严禁对公网开放该端口。

Tailnet 管理员目前未启用 Tailscale Serve；启用后可将入口升级为其 HTTPS 地址，并重新构建 APK 或在 App 设置中更换 URL。生产数据备份位于日记独立数据目录中，环境文件不得复制回本机。

## 公网 HTTPS 日记入口（2026-09-26）

手机使用独立公网 `https://203.195.195.218`，不能使用 `http://203.195.195.218`（80 端口属于金融系统），也不能在未连接 Tailnet 时使用 `100.125.111.63:8020`。

- `diary-ip-acme` 在 IP 的 HTTP 80 保留日记证书的 ACME 验证路径；其余 HTTP 路径引用金融站点的 `/etc/nginx/snippets/nexus-blade-site.conf`，使用金融站点独立的 Basic Auth。配置模板为 `deploy/nginx-ip-acme.conf.template`，替换 `__PUBLIC_IP__` 后部署；更新前先备份旧站点，更新后运行 `nginx -t` 并重载。
- `diary-public-https` 监听 443，使用受信任的 Let's Encrypt IP 证书，将请求通过独立 Basic Auth 转发至 `127.0.0.1:8010`；未认证返回 401。
- 连接密码不写入代码、APK 或仓库，服务端只存独立的 `/etc/nginx/.htpasswd-diary` 散列，用户的真实密码仅存本机桌面凭据文件。
- IP 证书有效期约六天；使用 `/opt/diary-server/certbot-venv/bin/certbot` 签发，`diary-cert-renew.timer` 每日自动续期并在成功后重载 Nginx；续期 dry-run 已验证。不要改用旧版系统 Certbot 续签 IP 证书。
- 金融服务仍在 8000 和原 Nginx 80 站点；日记服务只监听 127.0.0.1:8010。Tailscale 8020 保留作为私网备用入口，不得向公网放行。
