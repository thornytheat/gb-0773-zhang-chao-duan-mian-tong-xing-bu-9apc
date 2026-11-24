# 涨潮断面通行簿深度登记

- 中型。用精确阈值交点及航行偏移求全程潮窗。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 潮尺读数采信 | 查重复刊头和隔离行 | `/api/stage/readings` | `app/modules/intake/readings.py` `app/modules/intake/service.py` | `tests/test_readings.py` |
| M2 站点基准统一 | 复核孪站裁决 | `/api/stage/datum` | `app/modules/datum/resolve.py` | `tests/test_datum.py` |
| M3 水位阈值交点 | 查看来源点和交点 | `/api/stage/crossings` | `app/modules/crossings/interpolate.py` | `tests/test_crossings.py` |
| M4 全程可行潮窗 | 查断面偏移后的区间 | `/api/stage/windows` | `app/modules/passage/service.py` `app/modules/passage/state.py` | `tests/test_windows.py` |
| M5 船期覆盖勾稽 | 回查申请时点和时长差额 | `/api/stage/coverage` | `app/modules/schedule/service.py` | `tests/test_coverage.py` |
| M6 航速排程 | 按船体下沉选保速或减速方案 | `/api/stage/plan` | `app/modules/plan/service.py` `app/modules/plan/speeds.py` | `tests/test_plan.py` |
| M7 批次留档复跑 | 同源复算、补录改算及归档查阅 | `/api/journal` | `app/modules/journal/service.py` `app/modules/journal/store.py` | `tests/test_journal.py` `tests/test_plan.py` |
| M8 潮窗证据签发 | 验证原件及报告摘要 | `/api/export/<id>` | `app/modules/proof/service.py` | `tests/test_proof.py` |

| TRAP | 现象 | 朴素处理后果 | 处理 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-02 | 潮尺 BOM | 站号列错认 | 消除开头 BOM | `app/modules/intake/readings.py` | `tests/test_readings.py::test_bom` |
| TRAP-04 | 分段重复表头 | 表头当读数 | 记录分段并跳过 | `app/modules/intake/readings.py` | `tests/test_readings.py::test_repeated_header` |
| TRAP-05 | 多余列 | 原件错位 | 隔离留原列数组 | `app/modules/intake/readings.py` | `tests/test_readings.py::test_wrong_width` |
| TRAP-07 | 潮尺 N/A | 以零插值 | 隔离并保留原值 | `app/modules/intake/service.py` | `tests/test_readings.py::test_sentinel` |
| TRAP-10 | 三分之一秒交点 | 临界比较漂移 | 有理数插值 | `app/modules/crossings/interpolate.py` | `tests/test_crossings.py::test_exact_fraction` |
| TRAP-11 | Z 与东八区同刻 | 重复时间点 | 统一 UTC 秒 | `app/clock.py` | `tests/test_datum.py::test_timezone_repeat` |
| TRAP-14 | 同时潮尺矛盾 | 后报覆盖 | 同键冲突全部隔离 | `app/modules/datum/resolve.py` | `tests/test_datum.py::test_conflicting_station` |
| TRAP-15 | 厘米、米混用 | 水深错档 | 按单位换算后加基准 | `app/modules/datum/resolve.py` | `tests/test_datum.py::test_normalize_unit` |
| TRAP-19 | 孪站同刻 | 顺序决定选站 | 显式优先级 | `app/modules/datum/resolve.py` | `tests/test_datum.py::test_station_priority` |
| TRAP-23 | 船期右端 | 重复归属 | 排除右端 | `app/modules/passage/service.py` | `tests/test_windows.py::test_half_open_end` |
| TRAP-31 | 静态吃水开快 | 浅段下沉被漏计，可行时段写宽 | 按 (kn/design)² 计下沉并重核余量 | `app/modules/plan/service.py` | `tests/test_plan.py::test_static_draft_would_pass_but_keep_blocked` |
| TRAP-32 | 减速后的到达时刻 | 沿用设计航速偏移，后续断面余量错档 | 偏移按 design/kn 缩放 | `app/modules/plan/service.py` | `tests/test_plan.py::test_offsets_rescaled_by_speed` |
| TRAP-33 | 迟到航速数据重算 | 覆盖旧簿、旧结论不可回查 | 新簿承接 parent，旧簿原件与潮窗保留 | `app/modules/journal/service.py` `app/modules/journal/manifest.py` | `tests/test_plan.py::test_late_speeds_recompute_keeps_old_archive` |
| TRAP-34 | 同一方案重复提交 | 反复留档 | 同输入按 run_id 去重，重试沿用原簿 | `app/modules/journal/store.py` | `tests/test_plan.py::test_same_speeds_retry_reuses_archive` |

海棠17窗口 3000 秒 = 1500 可行 + 900 不可行 + 600 缺证。潮尺接收 20 条数据，18 条格式采信，11 条进入断面判定，2 条格式隔离、7 条业务隔离。重复表头及空行单计。以分钟级实测样例演示，不覆盖未带偏移的当地时刻、曲线外推和实时设备连接。

## 航速排程

船期表只有申报吃水与富余。浅段快速航行时船体下沉（squat）更多，按静态吃水算会把偏浅时段写成可行。可选 `speeds.csv` 按船、按断面给出设计航速 `design_kn`、保速 `keep_kn`、减速 `slow_kn` 和设计航速下的下沉系数 `squat_coeff`；未提供时方案记为缺证（`decision=unknown`），原有潮窗与覆盖账不受影响。

- 每断面门槛 = 申报吃水 + 富余 + 该航速下的下沉，下沉 = `squat_coeff × (kn / design_kn)²`。
- 到达某断面的时刻 = 出发 + 该断面偏移 × `design_kn / kn`；减速后后续断面更晚到达，余量随之重算。
- 先试保速：申请时点起的当前窗口有可行出发即选 `keep`。否则试减速：若减速能在当前窗口通过，选 `slow`（减速吃当前窗口，代价是后续断面更晚）。两者当前窗口都过不了时，看下一趟高水：保速可行则在下一高水 `wait`/`keep`，否则减速可行则 `wait`/`slow`，潮尺未覆盖下一可行窗口则记为缺证 `wait`。
- 阈值交点沿用轨道化有理数插值，`windows`、`pieces` 以分数秒表达；每个断面给出深度、门槛、余量、航速、下沉与到达时刻，便于逐段复核。

迟到航速数据到达时，用 `POST /api/journal/<id>/rerun` 携带 `{"speeds": "..."}` 重算：结论变化生成新簿并在 `parent` 指向原簿，原簿仍保留当时的航速与潮窗可回查；同一输入重复提交按 `run_id` 复用，不新增留档。原簿也可继续用原航速复跑校验。
