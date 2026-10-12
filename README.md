# Firmware moves (79 built-in whole-body motions)

← Part of [g1-robot-moves](https://github.com/sondos-myi/g1-robot-moves): one move per branch. The `main` branch has the map.

Firmware **1.5.6** on our G1 has 79 whole-body motions built in: 10 dances (4 of them popping), plus greetings, pointing, talking gestures, hearts, celebrations and poses. **Unitree's own controller plays them and keeps the robot balanced.** No debug mode, no RL policy, no training.

You start one with a single call: `LocoClient.SetFsmId(550000 + <motion id>)`. For example, `SetFsmId(550604)` plays 604, the robot dance.

> **Status (2026-10-11):** 543 (salute), 604 (robot dance) and 534 (hands on hips) are confirmed on the real robot. 534 is on the remote as **L1 + R1 + A** (`hands-on-hips` branch). Seven more were played on 2026-10-06, but their results weren't written down.

---

## Rules

1. **Start from run mode (FSM id 801), with the robot standing still.** That's the only state we've tested. In the motion the FSM id is 550; when it ends, the robot goes back to 801 by itself.
2. **Dances move the feet.** Keep 2–3 m clear around the robot, and keep the gantry rope slack for first runs. The team found some dances "very bold": try a new one on the gantry first.
3. **Never use the System motions** 401, 402, 403 (lie down / get up from the floor). 402 makes the robot lie down.
4. **There's no sim preview.** The motion data lives on the locked main board (PC1). The API only gives names and lengths, and nothing is on the Jetson.
5. Not known yet: whether `SetFsmId(801)` stops a motion halfway.

## List the motions (read-only)

On the robot, in `~/g1_walk_trigger` or anywhere with `unitree_sdk2_python`:
```python
import json
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

ChannelFactoryInitialize(0, "eth0")
loco = LocoClient(); loco.SetTimeout(3.0); loco.Init()
loco._RegistApi(7100, 0)
code, data = loco._Call(7100, json.dumps({"fsm_id": 550, "api_id": 1}))
print(code)   # 0 = OK
for mid, info in sorted(json.loads(data)["data"].items()):
    print(mid, info)
```
It returns `{motion id: {name, duration}}`.

## Play one

Robot in run mode (801), standing still, area clear:
```python
loco.SetFsmId(550604)   # 604 = robot dance, ~18 s
```
To start one from the remote with no laptop, use `motion_trigger.py` from the `hands-on-hips` branch and change `MOTION_ID`.

## Firmware shortcuts already on the remote

In run mode, a **double-tap** of a face button plays a firmware motion by itself: A = clap, X = air kiss, Y ≈ 4.9 s (left-hand wave?), B ≈ 23 s (a dance?). See [BUTTON_MAP.md](BUTTON_MAP.md).

---

## All 79 motions

Same list as the spreadsheet [docs/G1_Firmware_Motions.xlsx](docs/G1_Firmware_Motions.xlsx). **This file is the up-to-date one for the Tested column.** Meanings marked "guess" are translated from the firmware name.

### Dances
Whole-body dances. Feet move: keep 2-3 m clear, gantry rope slack for first runs.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 502 | `550502` | Popping dance | 38.6 |  | `vq_POPPING1_003_SY_09478d7c_G1_50hz` |
| 503 | `550503` | Popping dance | 25.8 |  | `vq_POPPING8_001_v1_G1_50hz` |
| 504 | `550504` | Popping dance | 30 |  | `vq_POPPING9_001_v1_G1_50hz` |
| 602 | `550602` | Popping dance (shorter version) | 18.3 | Played 2026-10-06, result not written down | `vq_POPPING1_002_SY_83b11255_G1_50hz` |
| 604 | `550604` | 机械舞 Robot dance | 17.9 | Yes: 801 → 550 (~18 s) → 801, 2026-10-06 | `vq_YSKJ_JIXIEWU3_001_XX_b1f11bf1_G1_50hz` |
| 506 | `550506` | "New ballet"? (guess) | 32 |  | `vq_YSKJ_NEWBALEI_008_v1_G1_50hz` |
| 601 | `550601` | Mocap dance (Take 074) | 27.8 |  | `vq_G1_2026_0527_143543_Take_074_Skeleton0.bvh_50hz` |
| 603 | `550603` | Mocap dance (Take 100) | 21 | Played 2026-10-06, result not written down | `vq_Take_100_Skeleton0_3ece638d_G1_50hz` |
| 605 | `550605` | 我要翻过雪山 "I want to cross the snowy mountain" song dance | 31.2 |  | `vq_YSKJ_WOYAOFANGUOXUESHAN_001_XX_f3f9bad0_G1_50hz` |
| 574 | `550574` | 迎宾 Welcoming-guests routine | 42.2 |  | `yingbin` |

### Greetings
Hello, welcome, bow, salute, handshake.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 507 | `550507` | Wave hello, left hand | 4.1 |  | `hello_left_hand` |
| 508 | `550508` | Wave hello, right hand | 4.9 |  | `hello_right_hand` |
| 509 | `550509` | Wave hello, both hands | 5 |  | `hello_both_hand` |
| 553 | `550553` | 双手打招呼 Greet with both hands | 6 |  | `vq_shuangshoudazhaohu` |
| 554 | `550554` | 双手欢迎 Welcome with both hands | 4.2 |  | `vq_shuangshouhuanying` |
| 568 | `550568` | 右手打招呼 Greet with right hand | 5.1 |  | `vq_youshoudazhaohu` |
| 572 | `550572` | 左手招呼 Greet with left hand | 5 |  | `vq_zuoshouzhaohu` |
| 565 | `550565` | Big wave above the head | 5.8 |  | `vq_wave_above_head` |
| 566 | `550566` | Wave below the head | 3.9 |  | `vq_wave_under_head` |
| 516 | `550516` | Bow | 4.9 | Played 2026-10-06, result not written down | `bow` |
| 543 | `550543` | 敬礼 Salute | 4.1 | Yes: 801 → 550 (~5 s) → 801, 2026-10-06 | `vq_jingli` |
| 552 | `550552` | Handshake | 1.9 |  | `vq_shake_hand` |
| 525 | `550525` | Handshake, right hand | 5.9 |  | `shake_right_hand` |
| 570 | `550570` | 自我介绍 Self-introduction gesture | 7.9 |  | `vq_ziwojieshao` |

### Pointing
Pointing and presenting.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 514 | `550514` | Present / point to the left | 5.4 |  | `gesture_to_left` |
| 515 | `550515` | Present / point to the right | 4.7 |  | `gesture_to_right` |
| 558 | `550558` | 双手右指 Both hands point right | 5.5 |  | `vq_shuangshouyouzhi` |
| 559 | `550559` | 双手左指 Both hands point left | 5 |  | `vq_shuangshouzuozhi` |
| 569 | `550569` | 右手前指 Right hand points forward | 5.1 |  | `vq_youshouqianzhi` |
| 573 | `550573` | 左手指向 Left hand points | 4.2 |  | `vq_zuoshouzhixiang` |
| 537 | `550537` | Right arm extended forward | 2.5 |  | `vq_extend_right_arm_forward` |
| 539 | `550539` | Push forward | 3.1 |  | `vq_forward_push` |
| 517 | `550517` | Presenting something with the hands | 10.6 |  | `hands_gesture_something` |
| 564 | `550564` | Look around / viewing? (guess) | 4.4 |  | `vq_view` |

### Talking
Emphasis and thinking gestures - useful while the voice bot speaks.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 511 | `550511` | Emphasis gesture, left | 4.2 |  | `emphasize_left` |
| 512 | `550512` | Emphasis gesture, front | 3.7 |  | `emphasize_front` |
| 513 | `550513` | Emphasis gesture, right | 5 |  | `emphasize_right` |
| 536 | `550536` | Emphasis | 2.7 |  | `vq_emphasize` |
| 510 | `550510` | Shrug | 3.5 |  | `shrug` |
| 560 | `550560` | 思考 Thinking pose | 4.3 |  | `vq_sikao` |
| 522 | `550522` | Hand on chin (thinking) | 8.2 |  | `rest_chin` |
| 547 | `550547` | Refuse / "no" | 2.3 |  | `vq_refuse` |
| 540 | `550540` | 抚胸确认 Hand on chest, "I agree / promise" | 4.8 |  | `vq_fuxiongqueren` |
| 548 | `550548` | Right hand on heart | 3.2 |  | `vq_right_hand_on_heart` |
| 549 | `550549` | Right hand on mouth | 2.8 |  | `vq_right_hand_on_mouth` |
| 567 | `550567` | 右切菜 "Chopping" hand motion, right (guess: explaining gesture) | 5.9 |  | `vq_youqiecai` |
| 571 | `550571` | 左切菜 "Chopping" hand motion, left (guess) | 6.5 |  | `vq_zuoqiecai` |

### Hearts & Kisses
Hearts and blown kisses.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 523 | `550523` | Heart shape above the head | 5.1 |  | `make_heart_upon_head` |
| 561 | `550561` | 头顶比心 Heart above the head (v2) | 6.6 |  | `vq_toudingbixin` |
| 545 | `550545` | Heart with right hand | 3.1 |  | `vq_make_heart_with_right_hand` |
| 524 | `550524` | Kiss, left hand | 5.7 |  | `make_left_kiss` |
| 526 | `550526` | Blow a kiss, both hands | 4.3 |  | `vq_blow_kiss_with_both_hands` |
| 527 | `550527` | Blow a kiss, left hand | 4.3 |  | `vq_blow_kiss_with_left_hand` |
| 528 | `550528` | Blow a kiss, right hand | 4.3 |  | `vq_blow_kiss_with_right_hand` |
| 538 | `550538` | 飞吻 Flying kiss | 5.8 |  | `vq_feiwen` |

### Celebrating
Celebration and fun.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 529 | `550529` | Both hands up | 2.6 |  | `vq_both_hands_up` |
| 530 | `550530` | Both hands up, leaning right | 2.8 |  | `vq_both_hands_up_deviate_right` |
| 550 | `550550` | Right hand up | 2.6 |  | `vq_right_hand_up` |
| 531 | `550531` | Boxing victory pose, both hands | 3.9 | Played 2026-10-06, result not written down | `vq_box_both_hand_win` |
| 532 | `550532` | Boxing victory pose, left hand | 2.6 |  | `vq_box_left_hand_win` |
| 533 | `550533` | Boxing victory pose, right hand | 2.6 |  | `vq_box_right_hand_win` |
| 535 | `550535` | Clap | 3.6 |  | `vq_clap` |
| 541 | `550541` | High five | 2.8 |  | `vq_high_five` |
| 542 | `550542` | Hug | 2.9 |  | `vq_hug` |
| 563 | `550563` | Ultraman ray pose | 3.5 |  | `vq_ultraman_ray` |
| 555 | `550555` | 双手拍肩? Patting shoulders? (guess) | 5.5 |  | `vq_shuangshoupaijian` |
| 557 | `550557` | Hands "flying" in front of chest? (guess) | 4.2 |  | `vq_shuangshouxiongqianfeishou` |

### Poses
Poses and idle behaviors.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 518 | `550518` | Hands on hips | 6.8 | Played 2026-10-06, result not written down | `akimbo` |
| 534 | `550534` | 叉腰 Hands on hips (v2) | 6 | Yes: L1+R1+A combo, 2026-10-11 | `vq_chayao` |
| 520 | `550520` | Arms crossed in front | 7.5 |  | `hands_cross_front` |
| 521 | `550521` | Hands behind the back | 7.9 | Played 2026-10-06, result not written down | `hands_cross_back` |
| 519 | `550519` | Scratching head, right hand | 7 |  | `scratch_right_head` |
| 551 | `550551` | Scratching head | 7.8 |  | `vq_scratch_head` |
| 556 | `550556` | 双手捂脸 Covering face with both hands (shy) | 4.7 |  | `vq_shuangshouwulian` |
| 546 | `550546` | 挠屁股 Scratching its butt | 5.6 | Played 2026-10-06, result not written down | `vq_naopigu` |

### System
DO NOT USE for now: 402 makes the robot lie on the floor.

| ID | SetFsmId | Meaning | Length (s) | Tested | Firmware name |
|---|---|---|---|---|---|
| 101 | `550101` | Return to stance | 0 |  | `stance` |
| 401 | `550401` | Stand up from lying on its back | 3.1 | **Avoid** | `vq_Y-qishen-faceup_001_get_up` |
| 402 | `550402` | LIES DOWN on the floor | 3.1 | **Avoid** | `vq_Y-qishen-faceup_001_lie_down` |
| 403 | `550403` | Stand up from lying face down | 5.5 | **Avoid** | `vq_Y-qishen-facedown_002_get_up` |

