# 手把手教你改《冠军足球物语》存档：金币和那四个资源数值随便填（附完整工具与原理）

> 适用：开罗（Kairosoft）《冠军足球物语》安卓版，包名 `com.leiting.soccer` v1.0.7
> 环境：MuMu 模拟器（Android 12 实例）+ 已 root 的 adb
> 声明：仅供**个人单机存档修改 / 逆向学习**。别拿去联机作弊，后果自负。

很多朋友想改开罗游戏的金币，网上教程要么过时、要么只说“用修改器”，遇到这种 **IL2CPP + 加密存档** 就抓瞎。我自己把一个档从头逆向到改成功，把完整过程和可复用工具都整理出来了。这篇专栏就当“交接文档”，让后面的 AI（或者你自己）照着做就能复现。

---

## 一、先看成果

我把顶部那四个资源（心 / 灯泡 / 奖杯 / 第 4 项）从 30 / 44 / 24 / 9 改成了 **9999 / 9999 / 999 / 999**，金币保持 9.99 亿级别。游戏正常读档、不报“下载失败”。

> ⚠️ 踩过的坑：**60000 会溢出显示**。那四个数值的显示格最多 4 位，而且后两项游戏自己会夹到 999。一开始我填 60000，结果四个图标全变白块——数值没丢，只是画不出来。所以安全值：**前两项 ≤ 9999，后两项 ≤ 999**。

---

## 二、存档是怎么加密的（核心原理）

开罗这代存档不是明文，是 **XOR + 44 字节循环密钥流**：

- 每个存档文件 = `8 字节头 + 密文`
- 解密：`明文[i] = 密文[i] ^ 密钥流[i % 44]`
- 加密（回写）：`密文[i] = 明文[i] ^ 密钥流[i % 44]`
- **密钥流就放在 `global-metadata.dat` 偏移 `0x30da18` 的连续 44 字节**，直接读出来，不用猜：

```
65 b6 48 ad 7a 08 2f 13 fd aa 4b e9 c6 fb 71 42
b7 49 1e 48 f1 d7 39 08 aa 32 ba ca 1b 27 f2 b5
b4 c0 ad b6 9e 7a 5d 25 18 90 65 64
```

校验方法：解密任意存档后，**前 4 字节必须是 `00 00 00 00`**（这是开罗存档的固定头），否则密钥流拿错了。

---

## 三、字段地图（改哪里）

以下偏移都是**解密后的明文偏移**：

| 内容 | 偏移 | 类型 | 说明 |
|---|---|---|---|
| 金币 | 1912 | int32 大端 | 存的值 = `游戏内金币 ÷ 10`（例：显示 999,824,740G → 字段写 `99982474`） |
| 资源①（心） | 15510 | int16 大端 | 显示上限 9999 |
| 资源②（灯泡） | 15512 | int16 大端 | 显示上限 9999 |
| 资源③（奖杯） | 15514 | int16 大端 | 保存时会被夹到 999 |
| 资源④（第 4 项） | 15516 | int16 大端 | 保存时会被夹到 999 |

---

## 四、最麻烦的一关：校验和（CRC）怎么绕

存档头部有 4 字节 CRC。我试遍了 `zlib.crc32` 各种区间、CRC64（poly `0xEDB88320`）各种范围，**都没能离线复现它的算法**。真实有效存档只有“游戏自己写出来的”那份，交叉验证也对不上公式。

**所以离线算 CRC 这条路放弃，改用“补丁绕过”：**

1. 游戏读档时 `ReadRecord` 会先 XOR 解密，再算 CRC 和头部比对，不一致就弹“下载失败”。
2. 我们把 `ReadRecord` 里“比对 CRC”的两个指令 **NOP 掉**（`libil2cpp.so` 里 `0x19A8030` 的 `cmp` 和 `0x19A8038` 的 `b.ne`，改成 `D5 03 20 1F`），游戏就接受任意 CRC 的存档。
3. **关键：Decode/Encode 一个都不要动**。这样磁盘文件仍是加密格式；你在游戏里点一次“保存”，游戏会用正确算法写出一份带有效 CRC 的标准存档。
4. 最后把 `libil2cpp.so` 还原成原版，收工。

> 原版 so 记得先备份：`/data/local/tmp/libil2cpp.orig.so`，md5 是 `7ae2ec859de81a653df975c3eb2cdcb9`。

---

## 五、完整操作流程（照抄）

### 1. 准备
- MuMu 开一个 **Android 12** 实例（Android 15 登不了这个游戏的账号）。
- 游戏里玩一会儿、存一次档。
- 装好 Python、Il2CppDumper（可选，定位字段用）。

### 2. 拉文件
```powershell
$adb = 'D:/Program Files/MuMu/nx_main/adb.exe'
& $adb connect 127.0.0.1:16416
# 存档
& $adb -s 127.0.0.1:16416 pull "/sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/0002" .\rs\0002
# so + global-metadata 用 pm path 拿真实路径后 pull
```
> Git Bash 会把 `/sdcard` 当本地路径转义，建议用 PowerShell 跑 adb。

### 3. 改值
```bash
python scripts/edit_save.py --save rs/0002 --global-metadata tools/global-metadata.dat \
    --money 999824740 --res 9999 9999 999 999 --out rs/0002.mod
```

### 4. 打补丁 + 装进设备
```bash
python scripts/make_crc_patch.py --so tools/libil2cpp.so --out tools/libil2cpp_crconly.so
```
```powershell
$so = '/data/app/~~xxxx==/com.leiting.soccer-yyyy==/lib/arm64/libil2cpp.so'
& $adb -s 127.0.0.1:16416 shell 'am force-stop com.leiting.soccer'
& $adb -s 127.0.0.1:16416 push tools/libil2cpp_crconly.so /data/local/tmp/crconly.so
& $adb -s 127.0.0.1:16416 push rs/0002.mod /data/local/tmp/0002.mod
& $adb -s 127.0.0.1:16416 shell "su -c 'cp /data/local/tmp/crconly.so $so; chmod 755 $so; chown system:system $so; restorecon $so'"
& $adb -s 127.0.0.1:16416 shell "su -c 'cp /data/local/tmp/0002.mod /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/0002; chown u0_a41:ext_data_rw /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/0002; chmod 660 /sdcard/Android/data/com.leiting.soccer/files/r08e8gyd/rs/0002'"
```

### 5. 进游戏读档 + **手动保存一次**
启动游戏 → 继续游戏 → 加载被改的槽（不会报错）→ 确认数值 → **点保存**。这一步让游戏写出标准存档。

### 6. 还原原版 so
```powershell
& $adb -s 127.0.0.1:16416 shell "su -c 'cp /data/local/tmp/libil2cpp.orig.so $so; chmod 755 $so; chown system:system $so; restorecon $so'"
```
再用原版 so 进游戏，确认读档正常。完事。

---

## 六、避坑清单

- **必须用 Android 12 实例**，Android 15 登不了账号。
- **Git Bash 跑 adb 要 `MSYS_NO_PATHCONV=1`**，否则 `/sdcard` 被转义。
- **每条 adb 命令先 `connect`**，守护进程偶尔重启会掉线。
- 改完**必须进游戏手动保存一次**再还原 so，否则盘上是错 CRC 的临时档，原版 so 读不了。
- 数值别超显示上限（前两项 9999、后两项 999），否则白块。
- 金币字段是 int32，显示上限约 9.99 亿 G，别顶太狠。

---

## 七、如果游戏更新了

偏移可能变。重新定位：
1. 重拉 `libil2cpp.so` + `global-metadata.dat`，`extract_keystream.py` 确认密钥流是否还在 `0x30da18`（大概率不变）。
2. `decrypt.py` 确认 `plain[0:4]==0`。
3. 金币：搜“游戏内金币÷10”对应的 int32 大端。
4. 资源：游戏里把某项 +1 存一次档，和上次解密文做 diff，唯一变化的 int16 大端就是它。
5. 补丁点：capstone 反汇编 `RecordStore.ReadRecord`，找 `CRC64.GetValue` 之后的 `cmp` / `b.ne`。

---

## 八、配套工具

完整脚本（解密 / 改值 / 打补丁 / 重定位）都放在 GitHub 仓库，零依赖，下载就能跑：
👉 https://github.com/<你的用户名>/soccer-save-edit-guide

里面有 `README.md`（更细的步骤与原理）和 `scripts/` 五个脚本。照着做，10 分钟改完一个档。

---

*如果这篇对你有用，点个赞收藏，让更多想学逆向的朋友少走弯路。有问题评论区见。*
