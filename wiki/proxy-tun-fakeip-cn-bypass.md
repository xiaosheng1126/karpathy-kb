---
schema_version: "1"
status: published
tags: [proxy, tun, fake-ip, clash, okz]
sources: []
created_at: 2026-06-23
updated_at: 2026-06-23
---

# 代理工具 TUN 模式下国内网站断网问题

## 适用场景

使用 OKZ / ClashX / Clash Verge 等开启 **TUN 模式**的代理工具，代理节点故障时，国内网站（Douyin、微信等）也一并无法访问。

---

## 根因

TUN 模式默认启用 **Fake-IP**，把所有域名 DNS 查询替换为虚假 IP（如 `198.18.x.x`）。

```
douyin.com → DNS 查询 → 198.18.0.55（Fake-IP，非真实 CN IP）
    ↓
规则 GEOIP,CN,DIRECT：198.18.0.55 不是 CN IP → 不命中
    ↓
MATCH → 走代理节点 → 节点挂了 → HTTP 000
```

**核心矛盾**：`GEOIP,CN,DIRECT` 是 IP 维度的判断，Fake-IP 破坏了它对国内域名的识别。

---

## 快速诊断

```bash
# 1. 看 DNS 是否返回 Fake-IP（198.18.x.x 段）
nslookup douyin.com

# 2. 看路由表是否有大量 198.18.x.x 路由指向 utunX
netstat -rn | grep "198\.18"

# 3. 看 TUN 接口是否存在
ifconfig | grep "utun"
```

---

## 解法

在规则列表末尾 `MATCH` 之前插入 `GEOSITE,cn,DIRECT`（域名维度匹配，不受 Fake-IP 影响）：

```yaml
rules:
  - ...（原有规则）
  - GEOSITE,cn,DIRECT          # 核心：域名维度识别国内站，直连
  - GEOIP,CN,DIRECT,no-resolve # 加 no-resolve，避免 Fake-IP 干扰 IP 判断
  - MATCH,🐟 漏网之鱼
```

**为什么 `GEOSITE` 有效**：它匹配的是域名字符串本身，不依赖 IP，Fake-IP 不影响它。

---

## OKZ 的持久化方案

OKZ 是封闭 App，每次重启/刷新订阅会重写 `config.yaml` 并生成新的随机 API secret，手动改的规则会丢失。

**解决方式**：用 launchd `WatchPaths` 监听 `config.yaml` 变化，自动重注入。

### 关键路径

```
~/Library/Application Support/io.V3.okz.app/clash/config.yaml
```

- OKZ 重启时才写这个文件（正常运行时不落盘）
- 文件里包含当前 API secret（每次不同）
- Clash API 端口：`127.0.0.1:19090`

### 脚本 `/usr/local/bin/okz-inject-rules.sh`

```bash
#!/bin/bash
CONFIG="/Users/becklong/Library/Application Support/io.V3.okz.app/clash/config.yaml"

sleep 4  # 等 OKZ 写完并加载

# 等 API 可用
for i in $(seq 1 15); do
    SECRET=$(grep "^secret:" "$CONFIG" 2>/dev/null | awk '{print $2}')
    [ -n "$SECRET" ] && {
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $SECRET" http://127.0.0.1:19090/configs)
        [ "$STATUS" = "200" ] && break
    }
    sleep 2
done

[ -z "$SECRET" ] && exit 1

# 注入规则（幂等）
python3 - <<'EOF'
config_path = "/Users/becklong/Library/Application Support/io.V3.okz.app/clash/config.yaml"
with open(config_path) as f:
    content = f.read()
if 'GEOSITE,cn,DIRECT' not in content:
    content = content.replace(
        '  - GEOIP,CN,DIRECT',
        '  - GEOSITE,cn,DIRECT\n  - GEOIP,CN,DIRECT,no-resolve'
    )
    with open(config_path, 'w') as f:
        f.write(content)
EOF

# 通知 Clash 重载
curl -s -X PUT "http://127.0.0.1:19090/configs" \
    -H "Authorization: Bearer $SECRET" \
    -H "Content-Type: application/json" \
    -d "{\"path\": \"$CONFIG\"}" > /dev/null
```

### launchd plist `~/Library/LaunchAgents/com.user.okz-inject-rules.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.okz-inject-rules</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/usr/local/bin/okz-inject-rules.sh</string>
    </array>
    <key>WatchPaths</key>
    <array>
        <string>/Users/becklong/Library/Application Support/io.V3.okz.app/clash/config.yaml</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/okz-inject-rules.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/okz-inject-rules.log</string>
</dict>
</plist>
```

### 安装命令

```bash
sudo chmod +x /usr/local/bin/okz-inject-rules.sh
launchctl load ~/Library/LaunchAgents/com.user.okz-inject-rules.plist
```

### 验证规则已生效

```bash
SECRET=$(grep "^secret:" \
  ~/Library/Application\ Support/io.V3.okz.app/clash/config.yaml | awk '{print $2}')
curl -s -H "Authorization: Bearer $SECRET" http://127.0.0.1:19090/rules \
  | python3 -c "
import json,sys
rules=json.load(sys.stdin).get('rules',[])
for r in rules[-5:]: print(r['type'], r.get('payload',''), '->', r['proxy'])
"
# 期望看到：GeoSite cn -> DIRECT
```

---

## 扩展：其他工具的方案

| 工具 | 方案 |
|------|------|
| ClashX Pro | Mixin 里直接加 `GEOSITE,cn,DIRECT`，订阅刷新不覆盖 |
| Clash Verge Rev | Override 配置，同上 |
| OKZ | 上述 launchd 自动注入方案 |

---

## 相关

- 时间：2026-06-20
- 设备：Andy Mac，OKZ + Tailscale（Tailscale 停止状态）
