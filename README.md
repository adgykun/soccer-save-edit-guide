# 冠军足球物语（开罗 / Kairosoft）存档逆向与改数值完整教程

> 适用版本：`com.leiting.soccer` v1.0.7（雷霆代理 / 开罗出品《冠军足球物语》）
> 平台：MuMu 模拟器（Android 12 实例）+ 已 root 的 adb
> 目标：把本地存档里的**金币**和**顶部四个资源数值（心 / 灯泡 / 奖杯 / 第 4 项）**改成任意想要的值，且改完游戏能正常读档、不报“下载失败”。

---

## 0. 先说清楚（重要）

1. **这是单机离线存档修改**，只改你自己账号、你自己设备上的本地文件，用于学习逆向与自用，请不要用于联机/作弊破坏他人游戏体验。
2. 本仓库**不附带任何游戏二进制**（`libil2cpp.so`、`global-metadata.dat` 都从你自己的设备/APK 提取）。脚本里写死的常量，全部来自对该游戏实际存档的解析与验证。
3. 存档有**校验和（CRC）**，而且我们**没能离线复现它的算法**（详见第 5 章）。所以本教程用的是“**补丁绕过 + 让游戏自己重存**”的稳妥路线，而不是“离线算对 CRC”。这条路已端到端跑通、可完全回退。

---

## 1. 环境与工具清单

| 工具 | 用途 | 获取 |
|---|---|---|
| MuMu 模拟器（网易） | 运行游戏，提供 root adb | 官网下载，开一个 **Android 12** 实例 |
| MuMu 自带 adb | 拉取/推送文件、装补丁 | `D:/Program Files/MuMu/nx_main/adb.exe` |
| Il2CppDumper（v6.7.x） | 把 `libil2cpp.so` + `global-metadata.dat` 反编成 `dump.cs` | GitHub: Perfare/Il2CppDumper |
| Python 3 | 跑配套脚本（解密/改值/打补丁） | 自带 `zlib/struct` 即可，可选 `pillow` 看截图 |
| capstone | 反汇编 ARM64，定位补丁点（可选，常量已给出） | `pip install capstone` |

> ⚠️ **必须用 Android 12 实例**，不要开 Android 15。该游戏（雷霆代理）在 Android 15 实例上无法登录账号，而 Android 12 实例可以正常玩、正常存档。

### 1.1 adb 连接

MuMu 多开实例的 adb 端口通常是 `16416` / `16417`（默认实例是 `7555`）。先连上再确认：

```powershell
# 用 MuMu 自带的 adb（注意路径空格要带引号）
$adb = 'D:/Program Files/MuMu/nx_main/adb.exe'
& $adb connect 127.0.0.1:16416
& $adb devices
```

> 坑：Git Bash 会把 `/sdcard/...` 当成 Windows 路径转义，导致 pull/push 失败。
> **解决办法**：用 PowerShell 跑 adb，或在 Git Bash 里加 `MSYS_NO_PATHCONV=1`。
> 另外 adb 守护进程偶尔会在命令间重启、连接丢失，**每个命令里都先 `connect` 一次**最稳。

---

## 2. 第一步：把游戏文件拉到电脑

### 2.1 拉存档

游戏存档在：

```
/sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/
```

里面是编号文件：`0000` 是槽位索引，`0001/0003`（旧档）、`0002/0004`（新档）是具体存档槽。一次全拉：

```powershell
$adb = 'D:/Program Files/MuMu/nx_main/adb.exe'
& $adb connect 127.0.0.1:16416 | Out-Null; Start-Sleep -Seconds 1
foreach ($f in @('0000','0001','0002','0003','0004')) {
  & $adb -s 127.0.0.1:16416 pull "/sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/$f" ".\rs\$f"
}
```

### 2.2 拉 `libil2cpp.so` 和 `global-metadata.dat`

- `libil2cpp.so` 在 app 私有目录（随机前缀路径），用 `pm path` 拿真实路径：

```powershell
& $adb -s 127.0.0.1:16416 shell 'pm path com.leiting.soccer'
# 输出形如 package:/data/app/~~xxxx==/com.leiting.soccer-yyyy==/base.apk
# so 实际在：/data/app/~~xxxx==/com.leiting.soccer-yyyy==/lib/arm64/libil2cpp.so
```

- `global-metadata.dat` 在 APK 内：`assets/bin/Data/Managed/Metadata/global-metadata.dat`。
  直接用 `adb pull` 把 base.apk 拉下来解压即可，或者从 `/sdcard/Android/data/com.leiting.soccer/...` 里找（部分版本会释放到 files 目录）。

> 先用 root 把 so 备份一份到 `/data/local/tmp/libil2cpp.orig.so`，后面还原要用：
```powershell
& $adb -s 127.0.0.1:16416 shell "su -c 'cp /data/app/~~xxxx==/com.leiting.soccer-yyyy==/lib/arm64/libil2cpp.so /data/local/tmp/libil2cpp.orig.so'"
```

---

## 3. 第二步：理解加密（这是核心）

### 3.1 文件结构

每个存档文件 = **8 字节头 + 密文**：

```
[ 0..3 ]  前 4 字节 = 密钥流前 4 字节（因为明文前 4 字节恒为 0）
[ 4..7 ]  校验和（CRC，算法未公开，详见第 5 章）
[ 8..  ]  用 XOR 密钥流加密的存档正文
```

### 3.2 加密算法：XOR + 44 字节循环密钥流

- 密钥流长度 **44 字节**，循环使用（period = 44）。
- 解密：`plain[i] = enc[i] ^ keystream[i % 44]`
- 加密（回写）：`enc[i] = plain[i] ^ keystream[i % 44]`

### 3.3 密钥流从哪来（已验证）

**密钥流就明文躺在 `global-metadata.dat` 的偏移 `0x30da18`，连续 44 字节**。直接读这 44 字节即可，不需要猜：

```
65 b6 48 ad 7a 08 2f 13 fd aa 4b e9 c6 fb 71 42
b7 49 1e 48 f1 d7 39 08 aa 32 ba ca 1b 27 f2 b5
b4 c0 ad b6 9e 7a 5d 25 18 90 65 64
```

配套脚本 `scripts/extract_keystream.py` 会自动从 `global-metadata.dat` 读出它并打印。
（备用方案：因为 `plain[0:4] == 0`，所以 `keystream[0:4] == enc[0:4]`；其余字节可用“已知明文投票法”还原，但直接从 global-metadata 读最省事。）

### 3.4 验证解密对不对

解密任意存档后，**前 4 字节必须是 `00 00 00 00`**。如果不是，说明密钥流拿错了或文件不是该游戏存档。

---

## 4. 第三步（可选）：用 Il2CppDumper 看字段名

如果你想确认“金币 / 资源”到底对应哪个类字段（而不是盲猜偏移），跑 Il2CppDumper：

```text
Il2CppDumper.exe libil2cpp.so global-metadata.dat
```

会生成 `dump.cs`、`script.json`。在 `dump.cs` 里搜 `money` / `SAVEL_MONEY` / `fanParam_` / `researchPoint_` 等，能定位到存档类（`GameData` 之类）的字段与偏移。

> 本教程已经把验证过的偏移直接给你（第 6 章），正常情况下**不需要**自己跑 Dumper。只有当游戏更新、偏移变了，才需要回头用 Dumper 重新定位。

---

## 5. 第四步：校验和（CRC）问题与“补丁绕过”方案

我们花了很多时间想离线算出头部那 4 字节 CRC，结论是：

- 它不是标准 `zlib.crc32`（在 `plain[8:]`、`plain[4:]`、各种连续区间都试过，对不上）。
- 它也不是 Il2CppDumper 里看到的 `CRC64`（poly `0xEDB88320`）在任意范围能匹配。
- 真实有效存档只有“游戏自己写出来的”那份，用它能交叉验证，但仍未反推出算法。

**所以离线重算 CRC 这条路放弃。** 改用更稳的“补丁绕过”：

### 5.1 思路

游戏读档时：`ReadRecord` 会先 `Decode`（XOR 解密），再算 CRC 和头部比对，**不一致就弹“下载失败”并拒绝**。
我们只要把 `ReadRecord` 里“比对 CRC”的那两个指令 **NOP 掉**，游戏就会接受任意 CRC 的存档。但 **Decode/Encode 保留不动**——这样磁盘上的文件仍然是加密格式，游戏读进来后、你在游戏里点一次“保存”，`WriteRecord` 会用正确算法写出一份带有效 CRC 的标准存档。之后把 so 还原成原版即可。

### 5.2 补丁点（已验证，文件偏移 == 虚拟地址）

`libil2cpp.so` 相关 LOAD 段里 **文件偏移 == 虚拟地址**，所以直接用下面的地址：

| 地址 | 原指令 | 动作 |
|---|---|---|
| `0x19A8030` | `cmp x0, x19`（比较算出的 CRC 与存档头） | 改为 `nop`（`D5 03 20 1F`） |
| `0x19A8038` | `b.ne` （不一致就跳去报错） | 改为 `nop`（`D5 03 20 1F`） |

> NOP 机器码 = `D5 03 20 1F`（4 字节）。改这两处就够，别的 Decode/Encode/CRC 计算调用**一个都不要动**。

配套脚本 `scripts/make_crc_patch.py` 会自动生成只 NOP 这两处的补丁 so（命名为 `libil2cpp_crconly.so`）。

### 5.3 还原

备份在 `/data/local/tmp/libil2cpp.orig.so`。改完让游戏重存后，把它复制回去、改权限、`restorecon` 即可（见第 7 章）。

---

## 6. 字段地图（已验证）

所有偏移都是**解密后的明文偏移**。

| 内容 | 明文偏移 | 类型 | 编码 | 说明 |
|---|---|---|---|---|
| 校验头 | 0–7 | — | — | 前 4 字节恒 0（解密后）；4–7 为 CRC |
| **金币** | **1912** | int32 | **大端** | 存的值是 `游戏内金币 ÷ 10`。例：游戏显示 999,824,740G → 字段 = `99982474` |
| 资源①（心） | 15510 | int16 | 大端 | 顶部第 1 个图标，显示上限 **9999** |
| 资源②（灯泡） | 15512 | int16 | 大端 | 顶部第 2 个图标，显示上限 **9999** |
| 资源③（奖杯） | 15514 | int16 | 大端 | 顶部第 3 个图标，游戏保存时会**钳制到 999** |
| 资源④（第 4 项） | 15516 | int16 | 大端 | 顶部第 4 个图标，游戏保存时会**钳制到 999** |

> int16 最大 65535；但**显示格最多 4 位**，超过就画不出来（白块）。而且后两项游戏自己会夹到 999。
> 实测：把四项都写成 9999，保存后前两项留住 9999，后两项被夹成 999。
> 推荐安全值：**前两项 ≤ 9999，后两项 ≤ 999**。

配套脚本 `scripts/decrypt.py` 会直接打印这些字段，`scripts/edit_save.py` 会按你给的目标值改并回写。

---

## 7. 完整操作流程（照抄即可）

假设你已拉好 `rs/`、`libil2cpp.so`、`global-metadata.dat`，并装好 Python。

### 7.1 解密看看当前值

```bash
cd soccer-save-edit-guide
python scripts/decrypt.py --save rs/0002 --global-metadata tools/global-metadata.dat
# 会打印：plain[0:4]、金币、四个资源
```

### 7.2 改值，生成加密存档

```bash
python scripts/edit_save.py \
  --save rs/0002 \
  --global-metadata tools/global-metadata.dat \
  --money 999824740 \
  --res 9999 9999 999 999 \
  --out rs/0002.mod
```

脚本会：解密 → 改 1912 与 15510–15516 → 重新 XOR 加密（头部 CRC 随便填，因为待会儿用补丁 so 读）→ 写出 `0002.mod`。

### 7.3 生成补丁 so 并装到设备

```bash
python scripts/make_crc_patch.py --so tools/libil2cpp.so --out tools/libil2cpp_crconly.so
```

```powershell
$adb = 'D:/Program Files/MuMu/nx_main/adb.exe'
$so = '/data/app/~~xxxx==/com.leiting.soccer-yyyy==/lib/arm64/libil2cpp.so'
& $adb connect 127.0.0.1:16416 | Out-Null; Start-Sleep -Seconds 1
# 1) 关游戏
& $adb -s 127.0.0.1:16416 shell 'am force-stop com.leiting.soccer'
Start-Sleep -Seconds 2
# 2) 推补丁 so + 改值存档到 /data/local/tmp
& $adb -s 127.0.0.1:16416 push 'tools/libil2cpp_crconly.so' '/data/local/tmp/crconly.so'
& $adb -s 127.0.0.1:16416 push 'rs/0002.mod' '/data/local/tmp/0002.mod'
# 3) root 替换 so
& $adb -s 127.0.0.1:16416 shell "su -c 'cp /data/local/tmp/crconly.so $so ; chmod 755 $so ; chown system:system $so ; restorecon $so'"
# 4) root 覆盖存档（注意属主/权限）
& $adb -s 127.0.0.1:16416 shell "su -c 'cp /data/local/tmp/0002.mod /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/0002 ; chown u0_a41:ext_data_rw /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/0002 ; chmod 660 /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/0002'"
```

> 上面的 `u0_a41` 是 `com.leiting.soccer` 的 uid，可用 `adb shell "su -c 'ls -ln /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/'" ` 查实际属主。

### 7.4 进游戏读档 + 手动保存（关键）

1. 启动游戏（MuMu 里点图标，或 `monkey -p com.leiting.soccer ...`）。
2. 标题画面选“继续游戏”，加载被改的那个槽。因为补丁 so 跳过了 CRC 校验，**不会再弹“下载失败”**。
3. 确认顶部数值变成你改的值。
4. **在游戏内点一次“保存”**。这一步让游戏用补丁 so 写出一份带**正确 CRC 的标准存档**。
   > 没手动保存就退出 → 盘上还是带错 CRC 的临时档，换回原版 so 后会读不了。务必先保存。

### 7.5 还原原版 so（收尾）

```powershell
$adb = 'D:/Program Files/MuMu/nx_main/adb.exe'
$so = '/data/app/~~xxxx==/com.leiting.soccer-yyyy==/lib/arm64/libil2cpp.so'
& $adb connect 127.0.0.1:16416 | Out-Null; Start-Sleep -Seconds 1
& $adb -s 127.0.0.1:16416 shell 'am force-stop com.leiting.soccer'
Start-Sleep -Seconds 2
& $adb -s 127.0.0.1:16416 shell "su -c 'cp /data/local/tmp/libil2cpp.orig.so $so ; chmod 755 $so ; chown system:system $so ; restorecon $so'"
```

然后用**原版 so** 重新进游戏，确认读档正常、数值正确、无“下载失败”。完事。

---

## 8. 坑 & 排错清单

| 现象 | 原因 | 解决 |
|---|---|---|
| 拉文件报 `permission denied` | 非 root / 路径错 | 用 `su -c` 读私有目录；或先从 app 内部复制到 `/sdcard` 再 pull |
| `pull` 把 `/sdcard` 当本地路径 | Git Bash 路径转换 | 改用 PowerShell，或 `MSYS_NO_PATHCONV=1` |
| `adb devices` 为空 / 连不上 | 实例端口不对或守护进程重启 | 确认用 Android 12 实例端口；每条命令先 `connect` |
| 进游戏弹“下载失败” | 原版 so + 错 CRC 存档 | 必须用补丁 so 读；或先让游戏重存出标准档再还原 |
| 顶部数值变**白块/空白** | 值超过显示上限（如 60000） | 改小：前两项 ≤9999，后两项 ≤999 |
| 后两项保存后变小 | 游戏把奖杯/第4项钳制到 999 | 这是游戏行为，不是你改错；接受 999 上限 |
| 还原 so 后读档黑屏/异常 | so 权限/SELinux 上下文不对 | `chmod 755` + `chown system:system` + `restorecon` |
| 金币显示异常 | 忘了“值 = G/10”，或溢出 int32 | 字段是 int32，上限约 21.4 亿；G 别超过 ~21.4 亿，**显示上限约 9.99 亿 G** |

---

## 9. 如果游戏更新了（泛化方法）

偏移可能因版本变化。重新定位步骤：

1. 重新拉新版的 `libil2cpp.so` + `global-metadata.dat`，重跑 `extract_keystream.py` 确认密钥流是否还在 `0x30da18`（大概率不变，因为密钥流是常量种子）。
2. 用 `decrypt.py` 解密新旧两份存档，确认 `plain[0:4]==0`。
3. **金币**：已知“游戏内金币÷10”这个值，在解密文里搜对应的 int32 大端，定位 1912 是否还准；不准就搜该值出现的位置。
4. **四个资源**：让游戏内把某一项 +1（比如用掉 1 点训练点），存一次档，和上次解密文做 diff，唯一变化的 int16 大端偏移就是它。
5. **补丁点**：用 capstone 反汇编 `ReadRecord`（Il2CppDumper 的 `script.json` 能查到 `RecordStore.ReadRecord` 的 RVA），找 `CRC64.GetValue` 调用之后的 `cmp` / `b.ne` 即可。

---

## 10. 配套脚本说明

```
scripts/
  extract_keystream.py   从 global-metadata.dat@0x30da18 读出 44 字节密钥流
  decrypt.py             解密某个存档并打印 金币/四个资源（自检 plain[0:4]==0）
  edit_save.py           改 金币 + 四个资源，重新加密写出（CRC 填空）
  make_crc_patch.py      生成只 NOP CRC 校验的 libil2cpp_crconly.so
  locate_fields.py       版本变动时，自动校验/重新定位字段偏移
```

所有脚本零依赖（只用标准库），`python scripts/xxx.py -h` 看参数。

---

## 11. 关键常量速查

```
游戏包名        com.leiting.soccer
存档目录        /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/
密钥流位置      global-metadata.dat @ 0x30da18 (44 字节)
密钥流          65b648ad7a082f13fdaa4be9c6fb7142b7491e48f1d73908aa32baca1b27f2b5b4c0adb69e7a5d2518906564
解密公式        plain[i] = enc[i] ^ ks[i % 44]
金币偏移        1912 (int32 大端, 值=G/10)
资源偏移        15510/15512/15514/15516 (int16 大端, 上限 9999/9999/999/999)
补丁点          libil2cpp.so: 0x19A8030 (cmp) , 0x19A8038 (b.ne) -> NOP (D503201F)
原版 so md5     7ae2ec859de81a653df975c3eb2cdcb9
```

---

## 12. 免责声明

本教程仅供**技术学习**与**个人单机存档修改**之用。修改存档可能影响游戏平衡与体验，后果自负。请遵守游戏用户协议与所在地区法律法规，不要将本方法用于联机作弊或商业牟利。
