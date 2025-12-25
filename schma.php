SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

CREATE TABLE `sora_content` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `source_id` varchar(50) NOT NULL,
  `file_type` varchar(10) DEFAULT 'v',
  `content` text DEFAULT NULL,
  `content_seg` text DEFAULT NULL,
  `file_size` bigint(20) UNSIGNED DEFAULT NULL,
  `duration` int(10) UNSIGNED DEFAULT NULL,
  `tag` varchar(200) DEFAULT NULL,
  `thumb_file_unique_id` varchar(100) DEFAULT NULL,
  `thumb_hash` varchar(64) DEFAULT NULL,
  `owner_user_id` bigint(20) UNSIGNED DEFAULT NULL,
  `source_channel_message_id` bigint(20) UNSIGNED DEFAULT NULL,
  `valid_state` tinyint(3) UNSIGNED NOT NULL DEFAULT 1 COMMENT '1待验证 / 4失效 / 9有效 / 20 下架',
  `stage` enum('','salai','luguan','no_thumb','no_file','pending','updated','prepare') DEFAULT NULL,
  `plan_update_timestamp` int(13) UNSIGNED DEFAULT NULL,
  `file_password` varchar(150) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;


ALTER TABLE `sora_content`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `source_id` (`source_id`),
  ADD UNIQUE KEY `id` (`id`),
  ADD KEY `idx_file_size` (`file_size`),
  ADD KEY `idx_duration` (`duration`),
  ADD KEY `idx_source_id` (`source_id`),
  ADD KEY `idx_id` (`id`);
ALTER TABLE `sora_content` ADD FULLTEXT KEY `content_seg` (`content_seg`);


ALTER TABLE `sora_content`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;




SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE `file_records` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `chat_id` bigint(20) DEFAULT NULL COMMENT 'Telegram 的 chat ID',
  `message_id` bigint(20) DEFAULT NULL COMMENT 'Telegram 的 message ID，群组触发后补全',
  `doc_id` bigint(20) DEFAULT NULL COMMENT 'MTProto 媒体的 document.id / photo.id / video.id',
  `access_hash` bigint(20) DEFAULT NULL COMMENT 'MTProto 媒体的 access_hash',
  `file_reference` text DEFAULT NULL COMMENT 'MTProto 媒体的 file_reference（hex）',
  `file_id` varchar(255) DEFAULT NULL COMMENT 'Bot API 的 file_id',
  `file_unique_id` varchar(255) DEFAULT NULL COMMENT 'Bot API 的 file_unique_id',
  `file_type` varchar(10) DEFAULT NULL,
  `mime_type` varchar(100) DEFAULT NULL COMMENT '媒体的 MIME 类型（如 "image/jpeg" 或 "video/mp4"）',
  `file_name` varchar(255) DEFAULT NULL COMMENT '文件名（只有 document/video 才有，photo 通常无）',
  `file_size` bigint(20) UNSIGNED DEFAULT NULL COMMENT '媒体大小（字节数）',
  `uploader_type` enum('bot','user') DEFAULT 'user' COMMENT '标记此行由 bot 还是 user 上传',
  `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT '最近更新时间',
  `man_id` bigint(20) UNSIGNED DEFAULT NULL,
  `bot_id` bigint(20) UNSIGNED DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='Telegram 媒体 (document/photo/video) 索引表，支持私聊→转发 与 群组内部更新';


ALTER TABLE `file_records`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uniq_file_uid` (`file_unique_id`,`bot_id`) USING BTREE,
  ADD KEY `doc_id` (`doc_id`,`man_id`);


ALTER TABLE `file_records`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;
COMMIT;



SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE `file_extension` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `file_type` varchar(30) DEFAULT NULL,
  `file_unique_id` varchar(100) NOT NULL,
  `file_id` varchar(200) NOT NULL,
  `bot` varchar(50) DEFAULT NULL,
  `user_id` bigint(20) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;


ALTER TABLE `file_extension`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `file_id` (`file_id`,`bot`),
  ADD KEY `idx_file_unique_id` (`file_unique_id`),
  ADD KEY `idx_file_id` (`file_id`),
  ADD KEY `idx_bot` (`bot`),
  ADD KEY `idx_uid_bid` (`file_unique_id`,`file_id`),
  ADD KEY `idx_uid_bot` (`file_unique_id`,`bot`);


ALTER TABLE `file_extension`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;
COMMIT;



-- --------------------------------------------------------

--
-- 資料表結構 `document`
--

CREATE TABLE `document` (
  `file_unique_id` varchar(100) NOT NULL,
  `file_size` int(12) UNSIGNED NOT NULL,
  `file_name` varchar(100) DEFAULT NULL,
  `mime_type` varchar(100) DEFAULT NULL,
  `caption` mediumtext DEFAULT NULL,
  `create_time` datetime NOT NULL,
  `update_time` datetime DEFAULT NULL,
  `files_drive` varchar(100) DEFAULT NULL,
  `file_password` varchar(150) DEFAULT NULL,
  `kc_id` int(10) UNSIGNED DEFAULT NULL,
  `kc_status` enum('','pending','updated') DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

--
-- 已傾印資料表的索引
--

--
-- 資料表索引 `document`
--
ALTER TABLE `document`
  ADD PRIMARY KEY (`file_unique_id`),
  ADD KEY `file_unique_id` (`file_unique_id`);
COMMIT;


CREATE TABLE `photo` (
  `file_unique_id` varchar(100) NOT NULL,
  `file_size` int(11) NOT NULL,
  `width` int(11) NOT NULL,
  `height` int(11) NOT NULL,
  `file_name` varchar(100) DEFAULT NULL,
  `caption` mediumtext DEFAULT NULL,
  `root_unique_id` varchar(100) DEFAULT NULL,
  `create_time` datetime NOT NULL,
  `update_time` datetime DEFAULT NULL,
  `files_drive` varchar(100) DEFAULT NULL,
  `hash` varchar(64) DEFAULT NULL,
  `same_fuid` varchar(50) DEFAULT NULL,
  `kc_id` int(11) UNSIGNED DEFAULT NULL,
  `kc_status` varchar(10) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

--
-- 已傾印資料表的索引
--

--
-- 資料表索引 `photo`
--
ALTER TABLE `photo`
  ADD PRIMARY KEY (`file_unique_id`),
  ADD KEY `file_unique_id` (`file_unique_id`);
COMMIT;



--
-- 資料表結構 `video`
--

CREATE TABLE `video` (
  `file_unique_id` varchar(100) NOT NULL,
  `file_size` int(13) UNSIGNED NOT NULL,
  `duration` int(11) UNSIGNED DEFAULT NULL,
  `width` int(11) UNSIGNED DEFAULT NULL,
  `height` int(11) UNSIGNED DEFAULT NULL,
  `file_name` varchar(100) DEFAULT NULL,
  `mime_type` varchar(100) NOT NULL DEFAULT 'video/mp4',
  `caption` mediumtext DEFAULT NULL,
  `create_time` datetime NOT NULL,
  `update_time` datetime DEFAULT NULL,
  `tag_count` int(11) DEFAULT 0,
  `kind` varchar(2) DEFAULT NULL,
  `credit` int(11) DEFAULT 0,
  `files_drive` varchar(100) DEFAULT NULL,
  `root` varchar(50) DEFAULT NULL,
  `kc_id` int(11) UNSIGNED DEFAULT NULL,
  `kc_status` enum('','pending','updated') DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

--
-- 已傾印資料表的索引
--

--
-- 資料表索引 `video`
--
ALTER TABLE `video`
  ADD PRIMARY KEY (`file_unique_id`),
  ADD KEY `file_size` (`file_size`,`width`,`height`,`mime_type`),
  ADD KEY `file_unique_id` (`file_unique_id`);
COMMIT;


CREATE TABLE `animation` (
  `file_unique_id` varchar(100) NOT NULL,
  `file_size` int(13) UNSIGNED NOT NULL,
  `duration` int(11) UNSIGNED DEFAULT NULL,
  `width` int(11) UNSIGNED DEFAULT NULL,
  `height` int(11) UNSIGNED DEFAULT NULL,
  `file_name` varchar(100) DEFAULT NULL,
  `mime_type` varchar(100) NOT NULL DEFAULT 'video/mp4',
  `caption` mediumtext DEFAULT NULL,
  `create_time` datetime NOT NULL,
  `update_time` datetime DEFAULT NULL,
  `tag_count` int(11) DEFAULT 0,
  `kind` varchar(2) DEFAULT NULL,
  `credit` int(11) DEFAULT 0,
  `files_drive` varchar(100) DEFAULT NULL,
  `root` varchar(50) DEFAULT NULL,
  `kc_id` int(11) UNSIGNED DEFAULT NULL,
  `kc_status` enum('','pending','updated') DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

--
-- 已傾印資料表的索引
--

--
-- 資料表索引 `animation`
--
ALTER TABLE `animation`
  ADD PRIMARY KEY (`file_unique_id`),
  ADD KEY `file_size` (`file_size`,`width`,`height`,`mime_type`),
  ADD KEY `file_unique_id` (`file_unique_id`);
COMMIT;

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE `bot` (
  `bot_id` bigint(1) UNSIGNED NOT NULL,
  `bot_token` mediumtext NOT NULL,
  `bot_name` varchar(30) NOT NULL,
  `user_id` bigint(1) DEFAULT NULL,
  `bot_root` varchar(30) NOT NULL,
  `bot_title` varchar(30) NOT NULL,
  `work_status` enum('used','ban','free','frozen','') DEFAULT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

INSERT INTO `bot` (`bot_id`, `bot_token`, `bot_name`, `user_id`, `bot_root`, `bot_title`, `work_status`) VALUES
(7092286282, 'AAHFi9fIjhY73GNKPgTjhsfwak12PljJvj0', 'afu002bot', 6941890966, 'afubot', '阿福(分类)', 'used'),
(7352783345, 'AAF8rkBQFpqbZ-C8BxIlaKUyqxzpHvv8_ZA', 'DavidYao812Bot', NULL, 'david', '耀庭', 'used'),
(6746469283, 'AAFnQUKIRnEUS5d-i16-gnt-FTNU3-j3xJg', 'has_no_access_bot', 5370120299, 'gusmama', 'gusmama', 'used'),
(7642467983, 'AAEe1bD9KNDpgprVMUh0gX2hLq66jVc3GhI', 'Juhuatai013bot', 7785042826, 'juhuataibot', '资源发布器', 'used'),
(7776819011, 'AAGMIT5eCBLOrueFQdrrqt-7SAfzKRzlBAA', 'ztdMiWen013Bot', 6625079627, 'ztdMiWenBot', '资源集散收集器', 'used'),
(7361527575, 'AAFnj832MChx30Ewf_GeB6mG_QL58bcl38A', 'Qing001bot', 6941890966, 'qingbot', 'QQ赢政', 'used'),
(7503122009, 'AAGluxzJtikbJtpsOeELqbcoSNcwXMNstlw', 'whaleboy013bot', 6625079627, 'whaleboybot', '小鲸鱼弟弟', 'ban'),
(7529315501, 'AAEdURP_m-femCI_JQ_H6TJ00fY3KVzsIoI', 'xiaojuhua010bot', NULL, 'xiaojuhuabot', '菊次郎弟弟', NULL),
(7358594899, 'AAEVTENrsm9lLqQxyhleq6LsTebLniyEu_g', 'xiaolongyang001bot', NULL, 'xiaolongyangbot', '', 'ban'),
(7463497642, 'AAFNpM3CCmjWZPAM8QPels5VwxlCU1KOGdw', 'xiaoxun807bot', 6084879704, 'xiaoxuan', '小轩', 'used'),
(7559710758, 'AAGRs_TtwTdrDNzYo-PNNw9Jf3iLHIq-UB0', 'xljdd012bot', 6712323637, 'xljddbot', '小懒觉弟弟', 'ban'),
(8181365246, 'AAGRVMwIB3DtFkGDTAYN2j-ZaEAYshoskSY', 'xxbbt1109bot', 7506897700, 'xxbbt', '棒棒糖', 'used'),
(8119578983, 'AAGG9TUOgi256Vd8X3faNMFQtZb3_nSZ1a0', 'ztd006bot', 6255354275, 'ztdbot', '小班弟弟', 'used'),
(7423378419, 'AAHwwHYHC-aK6-hN8Rb4XDSxhsWF7FNf3IE', 'ztdbeachboy013bot', 7785042826, 'ztdbeachboybot', 'Beach Boy', NULL),
(7470050860, 'AAFXPqq-5XGjyu08u-FSgxsUG3NYPWA4AAA', 'ztdBlinkBox013Bot', 7785042826, 'ztdBlinkBoxBot', '密文兑换中心', 'used'),
(7904289642, 'AAG2KcdDShPHqcCHp1BxYA0J2GetDJliwxY', 'ztdboutiques015bot', 7770953799, 'ztdboutiquesbot', '精品视频收集器', 'used'),
(7569689361, 'AAFa-Ic-8rQxYQNKzNrooZvR3rVf65Gh0ck', 'ztdg015bot', 7770953799, 'ztdgbot', '尝精阁套图收集器', 'used'),
(7228766174, 'AAEvVXlEJp5SPETFM5wLWkwQqpJEsoY60MU', 'ztdHelpCenter010BOT', NULL, 'ztdHelpCenterBOT', '正太岛街道办', NULL),
(7481088510, 'AAEu2hAKZ4TcqfbyRplXtklK2Wa1zB9Se7M', 'ztdmover001bot', 6941890966, 'ztdmoverbot', 'Mover', 'used'),
(7263955009, 'AAHwpn_HnTrmzIJEENjCqTDd2wXswArwOuQ', 'ztdreporter014bot', 7369962323, 'ztdreporterbot', 'Reporter', 'used'),
(8013314243, 'AAHJwbTGY09_j_966PdYFqt-5b-LDx_3V_4', 'ztdsailor012bot', 6712323637, 'ztdsailorbot', '正太岛小水手', 'ban'),
(6997218355, 'AAFDzd38c6eu01i0keIsfPVE2INMhLvpZmk', 'ztdStone009BOT', 7422864702, 'ztdStoneBOT', '石头汤收集器', NULL),
(7724630586, 'AAFYZ1Oim55HMscFeZVqcDxYay0waOrx-Yg', 'ztdv014bot', 7770953799, 'ztdvbot', '菊花台视频收集器', 'used'),
(7419440827, 'AAHLYxsJ74ZiYzqwX-n-ao_XoTGLAyGa7l4', 'salai001bot', 8004592128, 'salaibot', '萨莱', 'used'),
(7362260125, 'AAFyJZgOKau65GaEZFYn5fkn7jwjiQFrt9U', 'salai002bot', 8004592128, 'salaibot', '萨莱', NULL),
(7922404501, 'AAGP1bfxGepLJbT48iKzBfrdcQZKaewLqtk', 'ztdboutiques014bot', 7417416018, 'ztdboutiquesbot', '精品视频收集器', 'free'),
(7868483564, 'AAGahieqnnW4RTzJAd9ZXxIQwLe-wkCST-s', 'ztdg014bot', 7417416018, 'ztdgbot', '尝精阁套图收集器', 'free'),
(7426979711, 'AAF5I2O7f_D9yo7F9JRlIJEBG71v0WnmkAI', 'xlygrade05bot', 6504167109, 'xlygradebot', '', 'used'),
(7712653790, 'AAHo1m2CSxBNWKTKsRQwXX4WzRhW9wHqUFw', 'ztdthumb011bot', 7785042826, 'ztdthumbbot', 'Thumb', 'used'),
(7619749185, 'AAFk1oZRLu6UZF1E3qRA4ymqccpzA69CFJ0', 'youwen1112bot', 7227043930, 'youwenbot', '幼文', 'used'),
(7300770095, 'AAEW18BJa9JAyuNBCHj84zOJzB4En6D4Ix4', 'ztdcollector02bot', 6941890966, 'ztdcollectorbot', 'Collector', 'used'),
(7790220896, 'AAEGtuC5M7_dj_BY83wP-LzMMwU98Zc_Fvw', 'xxbbt2bot', 7205118382, 'xxbbtbot', '客服机器人', 'used'),
(7908601419, 'AAFLnoYw6ez8nyDYDEKLBghkSR1wMtuCJ5g', 'xxbbt3bot', 7205118382, 'xxbbtbot', '解说机器人', 'used'),
(7614859464, 'AAEff7nAhr5uJV7d_8rY0b0F3crlFWE43_4', 'WangYouWenBOT', 7228983960, 'WangYouWenBOT', 'WangYouWenBOT', 'free'),
(7812580664, 'AAFgk9ix4XtorH2dKMCWlM5R4MswW2mRCMw', 'DingYouWenBOT', 7228983960, 'DingYouWenBOT', 'DingYouWenBOT', 'free'),
(7767658198, 'AAGYKGyGn2_bpfP6ThD3hr2pR7A2IR0KJ-k', 'ztdactbot', 7397853295, 'ztdactbot', 'ztdactbot', 'used'),
(6457757567, 'AAHfl6XDXp8G8A9rrjuHteoCSxF3on0ERA0', 'DeletedAcconutBot', NULL, 'silence', 'DeletedAcconutBot', 'used'),
(7753111936, '1AZWarzMBu3iSpfPW9HUVZWbx760CPPRILxNhbg1b99eOEmZfR5RbJiWlBD2BxgJXGlmMuFc7jBTHAi8tGzQ0CEYwJKrcHdaiJmer9zec5Av4Oa5kEyv4LgaMeqHQXh3dQxUzUo6pEN1SIGd11DEI_tGyD_74n6Hetuq_cP4VzFS1ZUzsljiMobiVimu3FMhXbtfmy8zYJzQAIIMF66k0qlG1BJt2axCDG5XOcE4NC1A9X2Hys9yxHcs6T-9A4c6yy0ScKlYC0Fx7UQNeRsUV02gJDf3eBni6pAg9HK-X91S38hsYedHHUsMotBzoA4U_SC2pdC1KdDIJ1Hg-9CRtdnAexHNFBOI=', 'p_16173593362', 7753111936, 'p_16173593362', '顺丰快递', 'free'),
(7083406243, '29614663:aae4ae8959370f8ab9e23287a1238db9', 'example99875', 7083406243, 'man_bot', '例题', 'used'),
(7422581473, '28817994:34efb5ea40ab57fe1c1ca46d85fa24b2', 'sys3627', 7422581473, 'man_sys', '中山', 'used'),
(7600412139, 'AAFzI34KJktAeZUtjYwAWXYJ7fwFFQhdG3I', 'dyevatbot', 6725945300, 'dyevatbot', 'Dye Vat BOT', 'used'),
(7133772798, '1AZWarzMBu4PMi1zN3bBoQLJ9yT8Ujp-kcUG47IdbhsI9sCi7xjGNRaYQ9daYjlJmNqroGrwFQag4RaxPpl6AqFaw2zlz-u3l98Usd33GztorUVmmhcChew7Wi0RWMjRgYcrMRCTYu9c3bw7OvPU-1G1ABiErgGTUbE4cd_Kg6zkH6ZTX1XGX011rUrgjyjkAttCtTxw-RLOwt6ng9MKapZHWXYnpIPMKR2sihRzgg_3Y4fbpWoXGIeJXYrq0yvcBt3_4wahxbW5B9w5ANuv0OVqkpSMZWYBu4MVjfjM_IpN1Bbi7-w5EBABTu_DB8bBrn-_mWSj1VZe--44A6wdlZLfryoQ3on4=\n', 'dugujiushi', 7133772798, 'man_dugujiushi', '令狐冲', 'used'),
(8116549849, 'AAHAefuJQkZbWO-DE2RSZZE647mGYqGjvas', 'SalaiZTDBOT', NULL, 'SalaiZTDBOT', 'SalaiZTDBOT', 'used'),
(6272396309, '1AZWarzMBu7ZufD4PPGBSD42l3gJcG75X32Fr02kLxemFUakKfPGCVeWfDbdJ5uTO_gOYFsKwsJrx4IM9u4m-3-Rqbz1SuECL_8K6JZVFcao3YgNgmDLK_ZrvdA9uF_8VTmzDj3XLu7qx_aRbSxPdNve44ldHYd-mCWgkUE', 'shunfeng807', 6272396309, 'man_shunfeng', '顺风快递', 'used'),
(7496113118, '1BJWap1sBu502F9c7OXwIykK_M0_pLVuibpC6WeC0IOLrk4xc7qBPlk1qI2L0MHUFGNLUXoam1xFSS0qL-cw5rShEaKN_59sDM1vw-MIbkCrUBvmmeCns2joMGjY1TNVSCsDeCMQ8yrVzzESisxnNogvFpY6N7vRNNFss8qREiFA5-2s1map614By1HsI6k_F4nmKZVdlPSDsGP3JkGd3rO9lJLrxanTPOoCO53jrSW-WYv2mnH1oDzU3isLphvKyNeYTfkLcclRwFIuwYDj3zrCa4iejm4viyM-EWCYsrocTqRq_NpKV9epfPgmP2OUf7DnccTvwOWPQU29NqkTQdOln1Ws-uaM=', 'herendong', 7496113118, 'man_decoder', '何润东', 'used'),
(7567624231, '23239948:5a13434ad10da1d5e4e78f50b929dc0c', 'Bruce99678', 7567624231, 'man006', '布鲁斯', 'used'),
(7838360163, 'AAEACbyqta0JxDMjQcq14Yo5GBjWG89EhCA', 'ztdres001bot', 7397853295, 'ztdresbot', '仓库管理员', 'used'),
(7536293207, 'AAEUuxKguACqWRVsYX37etejFWGN5YoOCMk', 'xiaotongdengtabot', 7831617943, 'xiaotongdengtabot', '小童灯塔', 'used'),
(7375494875, 'AAFSDZeko59L9Vyps7P_YJTVXcOjwqeOZGI', 'fix807bot', 6810345316, '', '', NULL),
(6944815780, 'AAFoju7fW68V4HvWX5BHVRDyirmLWF-Av5g', 'whaleboy912bot', 6810345316, '', '', NULL),
(6493080022, 'AAHuFPKdhh8qYFjPLWxAYt76ikgzNMxg9iQ', 'autodecodder666bot', 6810345316, '', '', NULL),
(5731762561, '', 'nanbao_bot', 5370120299, '', '', NULL),
(6492821565, '', 'ourdkstorybot', 6084879704, '', '', NULL),
(6356620191, '', 'lxyguidebot', 6084879704, '', '', NULL),
(6135412681, '', 'memedaroot', 6084879704, '', '', NULL),
(7856295995, 'AAHgr-k7Q3EacPafTN_hmcaK_mWZL1ArzCg', 'xiaolongyang002bot', 7330834879, 'xiaolongyangbot', '小龙阳', 'used'),
(6389058760, '', 'xltrobot', 6084879704, '', '', NULL),
(6087119357, 'AAF86cjz9tIfSyOVdl_6HZBs2BklLPWiezU', 'getinvitationbot', 6287360702, '', '', NULL),
(6509642975, 'AAFDbdW2MWN50NnBvZ64nMcoOBL3NBaXbNc', 'sharedboy777bot', 6287360702, '', '', NULL),
(6690168483, 'AAGUs-IP9haRiBgTI1Fkw1amci0rZSq225g', 'gc807bot', 6245912121, '', '', NULL),
(6692410800, 'AAH9igwRwjhJfO42Hu6SDapjFQUOMTi3dZ0', 'joinhider12_bot', 6245912121, '', '', NULL),
(6002257095, 'AAFwqOTWvqnhDSTONkKGg00RN8QMIJEu4VI', 'xiaolongdd02bot', 6245912121, '', '', NULL),
(6433372595, '', 'gallery_compilation_bot', 6245912121, '', '', NULL),
(6016798727, '', 'ztsort765bot', 6245912121, '', '', NULL),
(7584746020, 'AAE0NV5xZ98ycwx-8QepOuv8JzjivFBAJ44', 'last_seen_a_long_time_ago_bot', 7227043930, 'last_seen_a_long_time_ago_bot', 'last_seen_a_long_time_ago_bot', 'used'),
(7544865217, 'AAHubDzvc4rrK9AAp2Jqhdclrd37fuvtw_M', 'chenchen807bot', 7227043930, 'chenchenbot', '宸宸', 'used'),
(6606902285, '', 'straymeow19', 620917081, 'straymeow19', 'straymeow19', 'used'),
(7572058495, 'AAE9xAhwK35JTOfIOW7-99nfMvzEhxRZhAE', 'tongjingbot', 7397853295, 'tongjingbot', '童精', 'used'),
(8076535891, 'AAExV1R7vjvBRFNDK8rp9anJwvmYhXmTfag', 'yanzai807bot', 7422864702, 'yanzaibot', '岩仔', 'ban'),
(7986489386, 'AAHLjwW3VcWpJHYTz1OY2CyhGx4kFw067Qo', 'ztdsailor013bot', 7227043930, 'ztdsailorbot', '正太岛小水手', 'used'),
(7715477841, 'AAE_KgyglTMuhf0zos5IbJpzfuo8lDUuIPo', 'xljdd013bot', 7227043930, 'xljddbot', '小懒觉弟弟', 'used'),
(7635473214, 'AAEta3IR6aHWBdhOvkclqiruLSFCbxaGCls', 'luzai05bot', 7606450690, 'luzai', '鲁仔', 'used'),
(7240086226, 'AAHisx2BsleMkSxd3qj4Lak-o4WruOb9vxE', 'freebsd66bot', 7606450690, '', '布施岛', 'used'),
(7643512833, 'AAF6I2wlJrGufUr-NgpYrYcWQbvqB4nGHPw', 'wait_up_bot', 7606450690, 'wait_up_bot', '不急导', 'used'),
(8102409598, 'AAGxFH_5crbHu4hYnihaB1ettQD7J9OYF64', 'luzai06bot', NULL, 'luzai', 'luzai06bot', 'used'),
(7460013239, 'AAHfXe19yX77s6WVPIXYgdAgrQS05dC_lJk', 'whaleboy014bot', 7477267239, 'whaleboybot', '小鲸鱼弟弟', 'used'),
(7522225022, '', 'luzai02man', NULL, 'luzaiman', '撸仔转发人型机器人', 'used'),
(7700830902, 'AAHOzACFHpWdI_-NJcaDgWdGJLkDxUebq1U', 'luzai01bot', 7767195791, 'luzai', '', 'used'),
(7556324628, 'AAG9pe2Lp_aZ0zTHQ5qMgqvAZmk_5AUfLn4', 'luzai02bot', NULL, 'luzai', '', 'used'),
(8004824489, 'AAHwY1K98Oa6NT8b5CJf6epY-fUgBzN8nJI', 'luzai03bot', 7999885657, 'luzai', '', 'used'),
(7521097665, 'AAF74kI9FYNMEAAlOtVp_2ocG5SItNA1i8U', 'luzai04bot', 7999885657, 'luzai', '', 'used'),
(7812424737, 'AAHV0ttn8uEc_3rOHRwwmndWYpXnp28oUXQ', 'luzai08bot', 7999885657, 'luzai', '', 'used'),
(7514761121, 'AAHsLvpr-p0-dmn2OhXTF2kqSqmQnriTcY8', 'luzai07bot', 5099426020, 'luzaibot', 'luzai07bot', 'used'),
(7840528094, 'AAGTm7sQ7t9eHrYTxjqo9ALeK_uQ7uDnXwY', 'GankPostBot', NULL, '', '', NULL),
(7586755746, 'AAHL66WEW4JWJj1XOOkcONCvnke1rJn_Lks', 'yooyao920bot', 8028896178, '', '', NULL),
(8159221389, 'AAHn4aMJMiYBTC6AYfzeGwf47KfTANxPPfc', 'ztdgrid01bot', 8028896178, 'ztdgrid', 'grid', 'used'),
(7400684433, 'AAFWUNazs1Ji8iqF7-XxU6SdXrzetxekJy8', 'ztdgrid02bot', 8028896178, 'ztdgrid', 'grid', 'used'),
(7643348597, 'AAGNb42uY9Vxqojr7Oj8be1TM7cMdPy25V4', 'ztdgrid03bot', 8028896178, 'ztdgrid', 'grid', 'used'),
(7950046998, 'AAHe4GBA10pm2_5O6AIsvYzosgpbjxcokK8', 'ztdgrid04bot', 8028896178, 'ztdgrid', 'grid', 'used'),
(8133675592, 'AAFcnglAodAAzGwwUit_wevkSGOZJ3xdf5c', 'ztdgrid05bot', 8028896178, 'ztdgrid', 'grid', NULL),
(7606450690, '1AZWarzQBu7Xrp9z0zF1P1WACh_VWstU-DqJ77zmRSb2KC-iC627FgFjmZlNLPv8_-HBc2CxLpSAAO0QkXf8ya3Q-O7RWICaCtmB9UXZ19wpZxLT0TwrseCctueEPh1AahpltHwBpLz4uMLshqrH10Mer5qeZbnesSoZhDIx8wXR0nUcvyifUbE4q9lc5fYSFl9u_HpwmdYGi_rYFUs8DhNBL5gQ1gX35ztaNZyEN42B2pDie80lbodDv187FawDfRytgR1hmhPG_gxHx-iTsuiYvPjYiMObeYO1y3o3YSGmEbVZNiunzGFQ-dgzKTCm2sjIH6IQYK-dxSDYfvGKengqll9xH1ow=', 'p_13026420786', 7606450690, 'p_13026420786', 'Rely', 'free'),
(8158392656, 'AAGxVevl430xhIbC3Y2pMM7rwUZtvoJwyGc', 'yanzai2015bot', 7767195791, 'yanzaibot', '岩仔', 'used'),
(7240323149, 'AAH0LvEej1AfkPNvhtFaXK8CEi-0cxi7YK8', 'lypanbot', NULL, 'lypanbot', '龙阳盘', NULL),
(7551138377, 'AAHLrPubzsCw5_iyxxwYhLv0fr3WjvcSOc8', 'anan807bot', NULL, 'anan807bot', 'anan807bot', 'used'),
(7637046702, '1BVtsOJEBu1vNEJfm_4j1JldaXeFAAojod39toOxpDkukG0MJQ2Mcg54Pt3yMoYwMmHO6CsK39AIpO0bcQQwamT_srr8eu_K9EwuILokNB-r2EROPUPnqVMRgLOR7hnZaNnk24Xd4oZJ2uEUzh20Qk7ANt9zd-RjykgfCjLC9P8Ielt7UbXOJ0eI_eOzzjnaOKkUxeJRbmfQRg2a5JonPj8WQkK7SD9anPue0a_lGQI3hGXFT7gSH2G6_oYO6RicLBX0TpQXtEGyw2H-Kpyb65gKDpJlMw5LhosBIWy0PQWz01sIWYL4p_bjZqArDnkS_UNcRKBeN0vPw7zjBeyqS8cu9VWH2icM=', 'p_919827677026', 7637046702, 'p_919827677026', 'Hiwar🍭🎈', 'free'),
(7657047842, '1AZWarzoBu0D91w8QaYK-pgvVM-Drd8Xl7Y-BYs1y_GKHwrpzgvKybGkhKMay5YW7HbGl3vTcgmRjaYBbOcCpGJBombTLhCUuFJ74_7NGE7zigtDFKkFXDsdbOg7D0nzZIxoBjCLOvpsNDPSxJKg9SprdQLcvkHaeVbzxh_0lot5r4H5-NQMZaXjAeBiITvBBrWZ71dH78Q24iRmlqPaxDOAJvcxymC1Z1uoenqb-iz8cPWA5ew1clO55Ss0Cto48y3VvBZ9IREAZGU_TWRcVXThHdtSirgcgqT3zzZRagYoDMWeDHEVEtu-irbLVbEoowYASg1YEa7LCfqlMJYQffbouVN2Cm94=', 'p_14707422807', 7657047842, 'p_14707422807', 'ChesterKayla', 'ban'),
(7830179299, '1AZWarzoBu19WBvXhPgxVQgxiVe3PB8m9JPR053KBp3sfhyP77Iyx0F26PPWLw_FEuj2UIKqMsQy3EVRdRluBtE670bgJKKpa8p62C5rNg4n1Q2jkWMkaFFmQyISYvHhTCnbS2JJMcbuKDvwd8eT1xAcRSjYV4cFXjGiR1JVBtqWwxp3xIpCXZiVl56xTNYPCoE6F2Jnf2So0V-3ijEu_sbPG30f5YGp7jfCOhore74dtYTBUfA-ulVtdLtIcs1yaVM2RDfW5x_Msm_5zSWMpC53Z1khXcN9kVcOul36-raNeHUC-q89aCsukcij4vFw8SdEnjX8d4zfQXvyD6ATiULeq5K_UMAM=', 'p_14699400783', 7830179299, 'p_14699400783', 'FidoKing', 'free'),
(7709218569, '1BVtsOKEBu5myF2Sximl0CRSYNwassMVcQz-Tn99qO4Lx9ryp1aCd4-CpMLiS83C4UmPQ3dt9o1rww57kaoWFnxOvif048cgxUx9E-V9AV9l4ciHwkTSw1yd0Junt6IS52iMop7ZBAdMejMuCACgo1pNvmkktT57ZI7HDBDHHV_Nmh1Nyxmrf4rrLZi1n5KHQHa1AA9YuGnteqNsMrNmBBiUWEQGgxDFpYrGnW5Zc9zawkGyaPdT_7Q8Egy4AVIElMLliEw3YgYFj2F5Z-ZhOpQARybnRY-hYiE7Kazjktz4_eclN844BbOtNM0yb18jLHEbhkte8QitS_VRxIxqdI9bCvA7Nxpg=', 'p_919828036862', 7709218569, 'p_919828036862', 'YhfjdSaini', 'free'),
(7794660519, '1BVtsOKEBu3OAaZfqDGicjWI33fWp9qBE4RAfPsYD_pm_xsfrJypwZ_O5jsGWbmvsvkVVb_VDIP0ahr72XjzE7tVzMxcJ4r1B6_vH2x06aM5nVDeX7pCjX99WpFfILJ6kQH5iHxXvWRs62IK_kMYlJzzD87eULck3CD5WOOp_b8M3pZJ5hehbmpknLEv6H3cyj9c0rCVlaliVbHJCroze1iSUATktk7w_vV9v8RKH1mKJnWmyDmFhPQKbMEDWYWSXfSVp5JAgsjnV6c8SQHCGzvIQdtyZnWchpO3rZJGFJBZmqGzzL30-Y6pUIFbnQ3eVTPZCJGp9S30YhpKuE50KJ9j4JTD9dYY=', 'p_919827754539', 7794660519, 'p_919827754539', 'DarlingAllu arjun', 'free'),
(7794838477, '1AZWarzoBuxkZVV5JKx0Umw7NcwCksVSoXzbfjvUDiPnqe5t58M2ZTuQ35XzHYIxI0ptFhiMRzZsyZZXydJx8MwN4MS-FacfYFaqHFx2yuKZfcbMQyRUpFn5IadVWIUIIaAk8HUYe2Ugjq_ju6r1PWQyzNuHTo-pCWP9FEMuICIxmDePnl3NaQeCTJ4ol_3qtE4psFEGzccaN3DSz4KMou8-WU16euYQqGJY6IeXJ7286eXWRUOCXoJtca_xdz0JJMv4DWtjmq9xIiiZW0FMfcWdk4spq5Nd5Zef9yk8Psngail4pgYdpARebaMZ-Oh18f6CdnOVKORJXDzjFLq_yk8hudWzD1GA=', 'p_14699401395', 7794838477, 'p_14699401395', 'NATRichardson', 'ban'),
(7629569353, 'AAEL2FRIY34LSEE3_6AukCzHZjuxKWU-hoc', 'stcparkbot', 6725945300, 'stcparkbot', 'stcparkbot', 'used'),
(7793315433, '1AZWarzoBuzkl5b9QXdfveSuDLfAedSgIljoQNEmmZq29o_uPJG76A0g845CcG114nDUDeEsXV1x7sAjEP0mVnnDLrMZnxlpCwzP_RB3smglsIEHTAbs_yxltnd04jyGQtubrvDOcYan4PzX3hMBokW3lV_w3NQJ1mz2JRpfKhphpnPQy8LxAMdX9J_LF8VRfv37eL_GxTXg08wkJytIw4fXcKx8oCw-BGGKcF4QX7doJdQ-wL5h4_YJc41BL56s7WVW4j3Ie_prh_0rGC6MIVGYxOPmBmPfz7Z8KT_QCXI_rDhWPSkp1z2CVlSV1NaLvnmRZonLI_g5Dv1Vdju59nq4j36MtMCQ=', 'p_14707422896', 7793315433, 'p_14707422896', 'KelseyBailey', 'ban'),
(7539299814, '1AZWarzoBuwbA4NIBSBHMz-pO9GdgSi_zfi-m6PspLmPUf0TgMVuovxhQjp5nQa10qdUh2xNeOW2z8MThAswqBsfbH8DNNN4VC9SvLpLvNwe-ZRTYIimo0oeHwZtkvInbFJExpqelb6CVsg8K2hVjjEsVVl75ojac16nfTgUO7ZoTahP87K9H_-26lsNZeE-UAWKp5nbEV9lmOeW-rZ8grU1vEXds688o3anKT8XqBwTR2_UAs_aBRMl66E_AfYHl3ZOhRsJwNb_Gv6rPsFNkzPH_wFXqYEsMCmxMIafV5qF4d9gasbuckAo6n2WB9Is19lgyBDTnICzTNa1R3ehK4qXZ_GC55i4=', 'p_14707202046', 7539299814, 'p_14707202046', 'ClaySamuel', 'free'),
(7745627558, '1AZWarzoBu611yZVjzINvqsf4JkioLSIdZzDYYCTiElzZd8j1ctml1P_bgNbm7AoLJr1m8FRDgLIzOQVWqs_PyfhYLHUTc5Ad63iXqVmY7lv6S5xyKNs4u83cjBPK3F-A4SIKBMl725-zSaBjYZlJpwDwOdUKaydJbxW1PnIxuqhrLcLHs-CSve_BEZetBolPf32UDyomvkrcYQJc9-v-6ufEj9I_P4HD8sAGKIgLKgf6z9JrHo22h3LFI4W550d0nQyJW2sn7WhtAd8XN_N9tyNXQVVHZKf4Mmxw-uFPXbahsraxSODAuCDSOkn6oTDA6T8rKKGWHgAqsZ_5xLZScNQafKx90_k=', 'p_14707348379', 7745627558, 'p_14707348379', 'BorisCampbell', 'free'),
(7550420493, '1AZWarzoBuw8-Qiq-SPvu_6oIkTEOoivowFfQAuZTdpn7jO4yqiwtUuVmxJbpX6X9oydUQlqhTv6XBYGYFH3O4y1QzsB5cMA4eF9LOB_af69YyoBx0bJDfFxiRkajnjjMeetu9i-NLiIGhR6cevnZj2sgwqqVB2Z781hLRx5P3g8UIMrTcWwGwgaf9UqGHQU-QJimHjoP1oJkEEarrFrncnt3qqb54WfskX2H19F7YOgGnhjHc8X9ie3_ej5mv8zkSArzdkoTTTDVJFYuEidYvHz68LHNoqGPa7NNeV_DbxHeaGTJQ8_CuniweaN8kJcPyzD8JkWOTHpiHYvoTIKg35QoDHqtTMA=', 'p_14699234886', 7550420493, 'p_14699234886', 'MaximilianFlores', 'free'),
(7609075670, '1AZWarzoBu2foe4HxUEXIHu9F3Fh2XJH0gHr7ldQn7C81784qtlafgyOUK4UWCFa7VYMq8AmTTZZETSPQMp5LQLFweegMCydEewJJ0Dh3Maa97IluQCVG-MsuOqrIIB5IMdcKanYyiqmaE3JWdBgbhSiCjGiKtqiz0_KGDUlbQg-3JhNTNqAvs-FoUSbeIlJQeiPKBX72bVtnsnGy0oBS2igFTf-tThBFQvkD0S2sLtQEht-b7i1JWWH-3fIVi1aSoA-3t_6QHAcphuFV6ojideL-j-IU6gOFMJVRtm6SADFe6WAp5WGiZa3mMO37M_JzGNEropjqLfhPEnDqylD2vljTdWZ8MQA=', 'p_14699402653', 7609075670, 'p_14699402653', 'DrXP', 'free'),
(7812073524, '1AZWarzMBu1bm9JFS7JaFuBq-rybgPAuw_gri2K4E01N_jv8wsGc44cfZc_8yapWUiD32NsVrYIaXD_mkDfLxbIKfEspY5L5y-1iwwe2_nQEgQNTOETaT2G_LCBYlsUgFSm5ry4kaBt5r2a9xtlUMZc1j71wELmlfc4gcHzi5jHQ48uMD_SqsKOAntu714dGKrHmrPAPN4ErcqSRFLlCig-6qGaCHrW3nEOxYXRorLv1p6jXLDvtbl6H1nh45v6ml5AKPqFENBlhKdiRtMnJICMeyXhO9JEVJ-B4Ig6Kg3lg7D3DV-glVusydzzhPGkRBIjLdMWQ-hGripWMBo1xbTfn7vEJfU48=', 'p_14707422939', 7812073524, 'p_14707422939', 'WilburHernandez', 'free'),
(7985482732, 'AAEhiQfns57ZEpZ4UuoK5CmuJ2O58PKFb94', 'Queue9838bot', 7606450690, 'queue', 'Queue', 'used'),
(7635497441, '1BVtsOLcBuxbXkV2oR7HGxPgJ8sdGh611_ZHgzczAIkH5DLtKWekIvm97BgUO4UJBULl4qaAIxcArEotSaTeQftNLkvswCtzMryfYzNzSK_FWkEhFU5a_LbyMOkKif2EQ5Gp1VRXxewQCIW-5FiQ6Q1ZwnbDZ9GNFd1VFRQquYKMIj1E2N2mlLWv6rkXEwRmJ9CFlJiLS9BAp2ufx7ErBivBMaPqXJTjWyjWtv6VPVo0_OOtS9y_plwp0RVhva3ZnDKPnDcPDlUceBBKqh_7lf2_bEz_9nrf6kKtLgMZlR5t-faEXLj8Szx0iR-6iCeSWPjiGmTdf-jK-tfkWr-XehVK0PAT9R3w=', 'p_919827928902', 7635497441, 'p_919827928902', 'Wormhole', 'free'),
(7929704794, '1BVtsOLcBuwJHQOiosIEmUYUbocAaxYJgGbirlRpKF6XRX6B37ZjeHytDsxx86pZv-80ivCI1Tv_l6oBTuzbzUcIV4OXl2qiy9aZswkOywoQjPNYOWPM-QitbpUqcRl0JO5Sl30XttWCFTqLt1w23l-OF-Cjo5fqRvBWFSmlW5xtaFVdQ9vnnsSvH8LGM_pqc3oGH6lC2WDhHcZlPr6AOoeEa2DgVOPTrg5D0yt3WGaMNSfu1KkvwLxyXBnNo_9X7Tzzo3Pj96hr0P0Se-ObMqpArmHdINmzSSKtUIgZEeVd6wKAkhZrb4xoQM8QrfFAjsXW2OKVHZK7nk8NEiUnCqBO062aAtlE=', 'p_919827836773', 7929704794, 'p_919827836773', 'TrilakshyaMajhi', 'free'),
(8096543387, '1BVtsOLcBu5VmDy9ROHSoksCiIxzuzXVjqjKpMjvbKBGZU2AyJMwCcrFPFfm4w0QMGVGS7zMlb2hs1W5YTbRsa5j5LRY7vNxeitDHu38-xPB2WEZjCPlMLIhNHYyGY-Df90RIjS5AtJl9LZ99njcLnnI_lKi7qYAmjdkbu63f6RpulKDJj0gCAO4RTYws-c5wwqKt78eii5B8WdV1X0OYI_e4Pz1bFaudMTfWXy2bTZda7N18cnG5zZZuwQsV8ZTjPEb_k5v8DPuL8NZWq5FRGOS-9mOtNaps-Jtqa-ja-Xq8v8uogpdWAbFIMyVR5AyQUpavMgDEFKVBeJXTipaSOKry0SePWEY=', 'p_919827989396', 8096543387, 'p_919827989396', 'AdamSampson', 'free'),
(7571257711, '1BVtsOLcBu5Zz0yxxfuyaqfTinyMTH3SW1lCvT2RnYQ7AO9HVDNtdDEiMo1eVV-TU2DZO1vELMlY8LYGDWCW8SGI6u_izpdx-yeoZKFIpZoFRKFQ5FhT3bDVka1RLj4uW1RW3C4-43D3uwYS0yd4mNbx-bM9VSl7nxa2OKjCcUW52vbkWb3COranVW79BZZkPheeUf0URQIfHwoiSFlk1CtY6TXmjLpE_o2R3QgnW_xAbldRopWMUvCuy4wq9P7x6j1Uu_h-u85xyIGw3vkSL39XWlB3f-hgZVXBNSl6wnfMTI2ej7-qBTcSN7VpwCAnQMme5aXmxDDA9itY3AgTQml8FrUmgL84=', 'p_919827781497', 7571257711, 'p_919827781497', 'RudraMaharana', 'ban'),
(7832680623, '1BVtsOJcBu7wxv67IgW7YpIPeMO6l7q9JGc23bxr_3rv9DUkHjAZmgpVHUQ21bibOqNwXcY2lMitnS1DiZ5EWpxRPE6iqv3I23EHCXBg3z4VRiNkYgT2-DIP8tAsFgF8_8rH1S5b1SdQ2IlFDV-6ZDJUarPTjovbTojKJXiQ3XYq79Hm3LLQ7XZlDETTzT9KhgjjqcaCt36wyzTVqFK0iqMIRfo5TbFuBEvhNUrNn16YysCYY6ZMECymB-S9zGSSCYKS5LsutH6Q63i8rqZpsBwzECjMi77Lr8sVPGBi2oQcpmMKW5rZxv2KXlh8-lANbrNCtSmSIjkxYl9aVyje_tGleqmNsOQ4=', 'luzai09man', 7832680623, 'luzai09man', 'luzai09man', 'ban'),
(7252274964, 'AAFg_5wdUujhN2ZmKAF18qGA71S9jBEcCZI', 'ytdd807bot', 7250697651, '', '', 'used'),
(7371694973, 'AAF9VUXmhwZ87uOiN7B36nNAfTIhVppk2zo', 'wyt807bot', 7250697651, '', '小班弟弟', 'used'),
(7814118323, 'AAHf2z5RGoA9SFG466nRn3PjHowCEMOW-EM', 'mgr_bsd_bot', 7205118382, '', '大管家', 'used'),
(7316709617, 'AAG2qBbyTKx4EiBKRG3rxwOeP8KsCAILIa8', 'ztdgrid06bot', NULL, 'ztdgrid06bot', 'ztdgrid06bot', 'used'),
(919827677026, '1BVtsOJEBu6A8KlDJc511OGo3iBt-bZEwo-HDyLcoxqaVwmkXuHT8Ucl98GA05RgXWA4rta2aMeCCoJbZnoSq3J9ZR0I37CWiC7S_HO6Z8GxGP3B-K4CTBVYMBrdkYyJ8FOIFBkKFry0TbP5PSPbVrlvCPoi9r7nTu1Di6cl12yGDJnH8cNWqd6gyRQVv7CT5aqGahPE7T9nqEZDmdyfsw_ISV1AXEl-PomCsrP5PlUeGfeMwWlDddNcztSd1nYLsoz03O3t7HdhuwnboMGbegjVZ1eztkfRfZ7ZGKyZas7sD8Kxw_M6KpJU5IZcKSYnKajqSP1eP37d866G_FsRs0goEjX-iN_E=', 'hahatai777f32', 919827677026, 'hahatai777f32', '+919827677026', 'free'),
(8565969302, '1BVtsOLkBu8QtHMSX8PmQntS095H-mLDnESeWIIytxO7rALdOmYCE_G2VQ4jZ7RiMsPT7hc86CKPgoyZsz2AjloRx-VJFKBDEHIPZxMboqCs1kgKSHMI4JrOyck3yQ9guBO2eUF8H3EOSOuzruQkPU1JZbIo8dQ9LI6I_eVweLVt_xjVx5vB3WSLMLnQWcMI4FklmqKodPhi4a3cPVYH6TUdzej4TW2qnf51TwCV_Ad8GSFOBcekX-aZPF1E0gZ9_tQnP1nJfXc3hmHB_Zen-NJjoswiBzIMpataKvlS6j108kXcrd8NcP0gu5MS2grgqapoOe8rSgYgdvovMkA-PE4FE0_AyrfA=', 'p_6281313215181', 8565969302, 'p_6281313215181', 'fjfhhf', 'free'),
(8415566780, '1BVtsOJ0Buyz87Pl4vQE70Si4uRAJWgkE0ZvxD0zEzn_oqHSFkhfIVozOlMJRyuyMRPQQGM_4S6WGApDjTKkn9u43DC5QVL1DuD06XQNlozvWSQcxknx3j9Xq0zSUT-sI-sM1wscinmVvT2YZ0eRqLW14Aoe-QsFGt-J0EGvSqhhGiMQGaFYn3vVXPuHmsHYzH1kD-tREk9hWzrpkL15UQHxgh6ZbbquGZmlEyMtZaJrZGTPrQlMi_i5m7p90rZTDWr-RLCIwYPcX875jHp87br3ohd6ASnq_BulgdmUfANFTMSuqtkLexgB1iz3No0aLBB_V0XBYbPv78vpMmSQTKqAEud-KmyM=', 'p_6281313606618', 8415566780, 'p_6281313606618', 'urfuud', 'free'),
(8273722164, '1BVtsOJ0Bu3cwCc54MOcP9zYJunkdtJu57jzomptIwyP_PXok4c3aXzVsHmtTADBZJI0k-kxIc2Ndgo-RW-5VVBQ0qckIy3QOY3Vcd_PE2DT88oJVclENa3X5FvlrV50M8wsbELMGN_siCCA-Q8wq3MBn0cLZidU3ie9wGHeTN8m0s2iWLVKS3aK6InsFkJN7ZwuT2_LW-57b5B-IbQVtuHaeVEcqI0jZ51KgX-DrKOq2KZ8RRDWv1bMjNQN13n8QdBq5NRYf6bhnSPadixf8-m-iFX02F-XeD0KM1F9dOSciCCYeT0aEZfuyqtRoNA7dSBioErV1ZuX3voKdLCbw4ukpLgdvA6c=', 'p_6281313271541', 8273722164, 'p_6281313271541', '611', 'free'),
(8310668466, '1BVtsOJ0Bu1-y1P7ckQYNj4tKrghfSmep2uLBDKpQdq4vIVQPq9kdqmiK74My0W2ZQUtmUwtURfvOGDeV8Yclhi1QlXnu61XCMmalwRghhX4LN8wJ_gtt5OZtZ77OVTmrRjIEMHfbhIaT6zTsc4nf6h0OraHpVQ-HsGsuu5e6WPeoQQJCYS0Iy03avrTtaNlUk_BjRsFpvgCfOvzXwbqOILd1IVMed-3hHkIq6kZZXkCe78G3f0rwaoQo_OpxwFx6FOjRao4yBS_xx5JzH4vldsOoLp024PMw2RkQIZZLxxKKKHhDHghTZDENBnRYJ1Of9Ph_VgL9EZWsrfeO6GmcVmsQOCMAp_0=', 'p_6281313606551', 8310668466, 'p_6281313606551', 'gigif', 'free'),
(8530120429, '1BVtsOJ0BuxADtwh6H4NH5BP6M2OHk1zJbAqgQUUE57PBtryjUs8MrOzd9Md_Bb2pYwBiy4Ihkqk7s2hO2FPeep6M1oHxUmOXf6QNutyhFSMu_D7pv5Yb5UlhgrBqSZGpbczyDPOaPXIEQy9uxnytHGDmCnM22OX6lSFdCU5_SEkJSFp6eB6wkNlAOGhtGxZYhN-4IvnT726Y0SeHPM81lwld3u1vX3OWKfxuVRRfvO4rXHk-oC4uMJpKEv3CrEGqcom_cjZer0vp3Q-qSo9O3QvX5dQgf3UPdH-CoT_hSrzCZysaD70izPXrNWbgKBh3URIc7QgnQiThM4xJEnk9MBGQ17p3W6w=', 'p_6281313423779', 8530120429, 'p_6281313423779', 'hffuuf', 'free'),
(8507894898, '1BVtsOJ0Bu4XKfPwMN6gy1f1WVGlzuDf1ew9m9ZbtGK2853pROTm9kvMB1MF6sf_eizEryXMALzVT635R9Cw5iw8MeRz_ZXzXuVOjilBrm0qMj2F_9QyDt6ZTCtEYmKlBL_UBasSgjXSXN7KugR1M4LwsiCh-XVTaXwhtuE7yofgNG4bttkw75TiRPm2vzXKxoZG1ZTgSCpCO-KzGutBRJsgO5uGOh-38iJzckIVMvW8mbP6l4tKDl7mWLlBklly_od-7L8Gh_xQ8KuIn2yyADbHrn7ao-OhMpysPM3BkwDOCbiHzZCHFzk2vJSA23dL5aoEs8i-t9wvpvwtuRwkKdpW8jsU9pEo=', 'p_6281313606619', 8507894898, 'p_6281313606619', 'yduf', 'free'),
(8071967330, '1BVtsOJ0Buw-tWt_rNLhtdDk2UpEhqidUdWQJNd7o-v1ABSTpOEsZ7d9r6pgZA4nnIJQpmgh2s1izeNfxb-QLe5cGiXbzzUtO40yl2mewIbbXlwuwvy8CaSPXhJXdyl82Nd-vWY8_TsjrmImtQGGVk5QRj-b0Wxu3PRQ5iQ2juDkBBbYJ22HrZChglSxM8Dt_Fqh_jf8NORDM86DRNO4ogIn4wv4InQ7R9ZUln0v75qjWUMY8az4Pg_WRnhfD-KnX_cSqbDlza1CmZMBAePu_39CIbf0XXHWbWfBz1FFtGwCYNUQ54LY695cA9CF4fF8a5_rlGDher6_TeHh1Aq239p7LjvHmNSI=', 'p_6281313645457', 8071967330, 'p_6281313645457', 'hdydyz', 'free'),
(8452317249, '1BVtsOJ0Bu8DAYKugqBH_cg-boLmJcokpfNpbSOnV2HauyaFhwHiZXmGsZMatOc4pSiWYLhO0F_u13l3MNjMiRV55X8UELke3viGAJhCTXJFLj1ex1pqYWj82qrDWw8j4elQC_M6AAH_7M-RM7v-ylduhqxDgx4NdHH0i8NNpgbh5BGHR43KI6q0urm8fSLLFqwfSiwxBul_ZBCLya-AX065BylSMHw-BZNiAfT-Ir5eHXDMLvFA7LAyIxFdn4rJyL2yCMhV_lO17Z_TM_cn9E117kLIpSBBXl0gDYl-iNCvF1VN8hZeTQOsQUxWfujeypfrHFdwqkX5Zk3SlCJJDyswhtI1pmeY=', 'p_6281313645482', 8452317249, 'p_6281313645482', 'hdfhhd', 'free'),
(7952327982, '1BVtsOJ0Bu8KCV0He7wPSjUHXN4yt0MABby-DBfQMOQzBJ9VWxzC_K0frBAO1zRZFUUoyuSJ1D49Or-bXofj5-EPddGb2hr3zjWTcAR-C9iYlqlPS2WhQnXqvsJiUakxlYzmLUJR5NUglpQ3-8TqZtxGzhRD5nB7QzqrdJRsohhzPz76xGSxCe9S34Ds3q8peqcu05fEDG5jJo58iRadiF5xonhUopRlrZb7Du4nFEY9RcIyb50Cpze4SyW-tRP6Xc4bZ8wHtIEOyfCtUCeleC4sGSJr2Rg5Pkm1bP1Q-GHNWBaEhbU6GKtNmzGKkNYTHOkeLRNtBTapm41Rna_tHXG21c7JSh0o=', 'p_6281313606623', 7952327982, 'p_6281313606623', 'ydydyd', 'free'),
(7968329201, '1BVtsOJ0Buy1o8QmAg1QWdrJ_NXVPF31ehcYkAtPKet5EUmcBvVu_4u8yTSy_M4DH8uH9o8SMEAF0VUYO39eyy5g35RQpjo3dV5YNK-FB0GI4v4ZiGUSzVnfNCwN5CzuxYncYbk2nF98K0gBohi5IqHmQB3UBGXkSlCIMiDn1VPvEQGoEvrlQS3X1Zm0XwR-kTgUllbiIY7ZyZWlG3Z46GYz14VJ8tNvvzmbS8LcsnZRQyddYyzMnGXnu2XJ-uN_SWEQ3vkLbFwUUd_tOWFUMBb-jxb0vPRZ8YzJ-ic44wQF1dk0EGD1mg8UHVb5GK2nEUJ5KkieC0epJBIt5zSB5T6ekW5-NvXk=', 'p_6281313606678', 7968329201, 'p_6281313606678', 'chhcxh', 'free'),
(8452560729, 'AAFTczVqOtomFdJUIT47cacyT1fNzrS3TVU', 'LYAIBOYBot', 5099426020, 'LYAIBOYBot', '夜爱君', 'used'),
(8262120752, 'AAFIYco2rPV4JOFa4AGxBuIoCbxRUnh5Dpw', 'dreamdidibot', NULL, 'dreamdidibot', 'dreamdidibot', 'used'),
(8209962183, '1BVtsOJEBu0W0dg_b-8T5c1hLPBj6ctOQty8GhCZ29UfJBzZGDd0vfaHxSEWmfzERK4wzhE7Y9uEoMJx5tKNrlZIg-4IV18wcMiTL9_rS15dssicg2KJY5IndoedXp_AWTnJZ90h-9y0ouJOQzOktQ7Ex2hM5WcTR_7F0h_YuqP_3DinV4X_lQq_bEhSiyKBxShcTT5ji69kemEbV5HKuOHdiqwmfDmZ2ND5SzYA7OZ_NXqxwocV4EMi3Cr5gxtuDoqZXCyaOOI2YKkgSDfDZhsCqjgZtuYA-JQXnwvdtSlWO6-5VIrm7_OWYWLdfO0zwWY0Yup2gPM3cDnKlykbSk82J1kdzphA=', 'p_916303192358', 8209962183, 'p_916303192358', 'Bella🎧', 'free'),
(7364974834, '1BZWaqwUBu2rjSzkUaEafWkBPgXRZX3AVm7ot8yK6MGNysKeyqfwi5JZ-1j6WwkUgv50VZG2wTtPlDHyo84DhVr1OUHV2hnWSAbrYlmJ-pTkislfwAEzP_jnd6li7-NUOvvsTZqhduhlobqhSOJfRs0RQqk-99-MbGNUv2J7-RadC1uVD8E4y-CjUTFztYsXxYvaJarG0O5uuFzxtvo6pMr3VESWFW_1STH7slGFA3w7QzZ5qiTm6K_I94k-gmpvnuGJd2hAbDtEephx6I8QiaOlpk7IGFivVE_Fn5BCbdkXUGcKxaV6aNSjcO59L--FLDmqrb52EVHZa8FKpJh76HJFcX3IkJkQ=', 'p_916307603621', 7364974834, 'p_916307603621', 'Bella🍃', 'free'),
(8573406912, '1BZWaqwUBu6hvRlNWmYwi_CwQt_0fgtbWyomRSWqw2iEF_O1sq45QI8-sxN2Hb9UF0cpw1qfuGsBFKM7luH7s6zVvVbsmknikUTyZU1xpHUnv64QQjGpQLhh0H7nlQwAxb2rwop6yBESx9jtiqADv7JKNMtl0VsxR3orlU-o_sYb1r69XQUGeYbgUrjGb0HKBKfwyzKxYserm93Jv3F8gOI_GgXktKntOJlUgMGg3gYj4rJXKrkagGAyGmDLWju4Bp8x3ooSHlMo0JUUhnbBQhACPv7Z0JO4n5L3cd0Nc6a7RWbEGwugKODO2oJBMmuCwXZNeaAkIbzuaEjbYsf_N3koIjDoLz9A=', 'p_919387208577', 8573406912, 'p_919387208577', 'Bella🔥', 'free'),
(8294606397, '1BZWaqwUBuwlfMJfMmwxdk3Rqwu8IZ6chAle-W0EWYef6Wr7-WkfXeVc_l7xEife5ucrU9AU9euXHbFlew6t10Pqtq7JardOTTt5uy67fe2L0HYrHYj0EmLlS1n9RqjwfxDB7yW7tTPfgJMHFFC61hi9JgQXqbgiVecbaEMWfN_dXwf0l6XRG8edIES6gP8OEYnOr83QE3Jm3HHrpyM2w7s5gs2Yiex04mEArS07V5beCToafLs3ULYfIupUjpymbyKjX3AdkAlsSxhoEW3xwm994pfWG6_G4-CQTXaM715j9GIivpWViUmRVf86H_mab62Vh1MdoTdVu5HYOf5bwUgnnu_U1E0c=', 'p_919997674951', 8294606397, 'p_919997674951', 'Bella🦄', 'free'),
(8412377011, '1AZWarzQBuxVNTv5QaVaVfjK_rw3cHRkFAaYPtms9p5GhXWjn5216pAG92G8oa30ZuJi3ly5ZmTO-9SYMOTPTZUgpeCO65nyvOk5UxNzQSTBuUX4kUGyJ--9_AuM15eHx74tt4bMz5hJlzad2YhbxfzBjlVdV93caf3mFICaeWNoEUwhw8wS8WSxsLlDWMLj46sgp1lNHgAC2Xwr2BHP8l5vT-OSbsEqijwgi3kixz2CwUpnTWTDh841Y5HQZLFgYq4rpF6shDU2HCJamisx5k_QfGOclBQqZJ6MJJfGwaHThdtOh2Y1rjNbTdLwa__8CHM38tDLLz-KzukZDi2Si0qj8Dkxf7js=', 'p_573004944938', 8412377011, 'p_573004944938', 'MangisannyPrnd', 'free'),
(8342969408, '1AZWarzQBu1ao3Qk9PkUm7LGJx2kQqNDnq8FQIgjk9LWDWqqlTUsxKYhCB2_3MpFze4GbL_H681GVwzygcjekqYwvdNJAIHqpHZcANPqtqorh9ucFVDQgfvdIeUCou3UuB9h9NrWwNubRWU2AGcdc6cRGcpqL58yTbeZvDCrWf5UdgMy9jff03VA5H9xLPsn1XBookSZRr4r4P4uykDjSM_X19G1qO7BR-Vq2gZK3-oIrqHHUpDh7D8nO2osnoWFxp-MyaHOkyLT7qnGDM4BpI_JibiT8B1va3nO08ImabVPJsk3HwEVcefXov3XK6q4KrSPrkj5g-xYmJycm0FQFFQ4yugWIZ-8=', 'p_573004949228', 8342969408, 'p_573004949228', 'WaeberedHon', 'free'),
(8359445593, '1AZWarzQBuwyS7f-csR8cZRQVWn1K22LyGN1h4zzaVBymPw4JPMnzbB_efvj7s8baoktG057n-aTu4foXCUv3fmrCu6RTOckq5jtMHspKNg_IWtlXbxVwWLAwWdnGjwxfRVTq5pju_R2xiJ_XsQP0B4LffFybjJ5sADbD_w0RYYtvmbjYyDKyOKeay_boODFiN2A5qYqXHh5hWNr7qoo3kA7HLlzJkgOwpiW4XMiFRWuH6iuMkKSiOSV-qdzfYNmauqg_81olHLSoEClqhEeUaVc9LiBoV7DexVj4lszR3hFeqO5trRuJzUZneXS-C0iK7PmBj_3jIdrjJOlvalZhN9jE12xwbtM=', 'p_573004952212', 8359445593, 'p_573004952212', 'NeyneWir', 'free'),
(8284757152, '1AZWarzQBu6-42Ec05ZwX7j3uWxX5o0Yn2AMUQmKSW0ogTP3FEJ5C0rIkPb0MA9xJ2Egsoj8hLKjPDwyrNyGnGALWt6Curyrolt1KvuIsg-gyiNBi4G0MEUdgOCcGKNV2jks0OkLaYhvHCtK1GpOb-jg7TbM8CnFO-bjdtjjZbNrp4ZU9mgvndM3n8RZ4E7soUwmVwHbn9Gi3_VsGxD78t0gO2vjzXlaNitsWThgR__HiUA8Dl0qxwWQEL4dxVvqtfKTmU1jID18zrA5q5RL77FnNT_LHqOJFFjp0f31XH9o7jlQpPSTODRYiCiFQjd36WPCJoHMIOaLhOzKQxCZRmqE98Ugf3ao=', 'p_573004944622', 8284757152, 'p_573004944622', 'BricenanttelvoRyen', 'free'),
(7562550834, '1AZWarzQBu6xHwW7mG3GyuAQPgrcof8yX6-ZkeXglmzXNRjfBU3hP-gtDShAlhGhBA3x1SCbOhnlLGM4rb3gJeLzmlRpnDMGvP3fX0e2DHh7QDFbgWvydYwAfZpmJ4DQHvcviZom6mSfcSdn2dtYZFalqgncAwbRc8heQ0YjwJdi-p0dx4ExPZNGUTRNyd18onkgKcPh8ODUhGyCB1qMyV3aRkAcWB3JZ0OrG65ZNWmkIRpxLLEtZeFQDHtuuZR9kUmFB3Dw4auoVsGo0JUnkgmX10_VF08tikgHG0mMvCQrghv9WoPlSxul_BsBMrout9PBMime7SQsMwQFCyfHskGFfv-pG4Jg=', 'p_573004952115', 7562550834, 'p_573004952115', 'RotlyCodwer', 'free'),
(8354654498, '1AZWarzQBu0Vz19Pt3r9bg_5JLS-CXQIt_68ECqf3jIAJInpx2XBAj-gpsOmrGcL_R58Ai4VxBEoVuoSFw_HzgjzFjNG7Mwc2E0Z5eJLRGXIEkVQ454l1eW1ApCX9TghCrwrz5lH_HC14un3YtPDfNUfFF_e1wq6TDuUv4wSPwI_zX1uh_L0lGpNjjsxjm7A2v3DRs4fVud-44ZvingGd7o-NqMjwJyoMDA5_dfCtN_-Ue0b_f6LhOGiL6bG2mzdZkhciipnbbNOBwDKtLB0cGoiM6svqK-_8NoxQH18qWX9j7JHbQmtuoPOMHWGpWUdtzh4htG6SLcmLgpPsG2KvDHCl6_FXtrc=', 'p_13855124044', 8354654498, 'p_13855124044', 'ChristopherHogan', 'free'),
(8212846254, '1AZWarzQBu5NWLDPsOVbjk2wYHoaqIrOqGmzPzfitwTYCdYJ9h_C9Hom_a2_3B-iz0rlY3fjPT30NA8KwtoRot2-GaNfibFb1js2fn0ujQJ6Wz-Wxd3kAhC1ebXrx0Kkf3gHYQbiOe4k1NhNj4UBZHWxJCdOH8TiyvIoS3FTWlr7g9zSiFrgwmuLBALFHNDkUdO4Z4ORd7ojcPhMFObZTVI3vrs8HOFt1EJagB9DtW6wH-EXixV8YbGzQ8ILudiO_CMSDWfStEHVZhbTnrpAljCpZ1IhHPW-K9Q8wRJlajZgoLHxIsr7NCw1TDcEJwTU6f7zklaHu3Tyb7mG9nBwIpb-lX96xUR8=', 'p_13855107503', 8212846254, 'p_13855107503', 'DeanSmith', 'free'),
(8221257978, '1AZWarzQBuwzQ5Ts7SlWTHNK3erXXxj_9qSnYcN3MW-m-LaEEKBHa-nd8ujgi6VNR3kSqNKZ6KdPSNGLncLWQAy7nnRdXA6RpdxSWjcUfhSpqF-QOBnvka4cWjlPHGqFVmNsshSjA_5nHQlcXQRsWeS1xi5wV8w7ihTodDm6zKqTMtIgLbAuuefzLLkfl25U1AiVvL9iiiwARTHadAX_smTG5UK5wBMoQa7YzhxFwPt2FpVAns4m03xdHWwk3zn5yb_XqxYiVZLqa0K4Kux6RniJXm-pMlMeCzti1EXDw4lH9b8YvmiP9IpH2S0nvw9GOxKaycpVGDM0nyzaowJ0LiCgCE5xbEbA=', 'p_13855214988', 8221257978, 'p_13855214988', 'MatthewPoole', 'free'),
(8208772192, '1AZWarzQBu29cdWnyUxt2lO-WnugzGKMj_8KnSYI6-FxcyMnv3TLsPHL8xD6xsqSI7uqYIrtgetsyNzeF7431CLPkewlSdLNP146lh6Z6TD3Zj16vkcjAh8qgc2byblsvVGeyrjaH5qnsVeXjcu2E_92ncd1TeYQzsw_NmEQ9Tt6SUOrrmtRkkXEj5W1D_QKVvL8J4EjLDW4OKT6y9KN4Z2izZT0og233Sfe-gb3gi1u0uPswSt3V3T3_klAazvPCOL29H2H7-HyWAWjz8KmqDIo4_DactMN_B6qK2y1lIiQ3RZpLxFG4EISj2uTDQneqfcPSUkEdKOijyXbAU_SHhOlLujuVVgs=', 'p_13855218163', 8208772192, 'p_13855218163', 'LisaMccarty', 'free'),
(8210149576, '1AZWarzQBu3uunGl2o1IOsuJ47moWjdhzOgjLpseLJrYoh3lbGrl9bMyg7VHl0_bWAeOi4uismP9tQFFhPvdwjZ2BCv6wVxn2hfRCIKIa-sYbztfT4DDLwCCs6TCnX0M172wob6K_8blKsj4f3LdGhliVZedluBwGQktF0-T7ABJS8avdhAWgDP1ESf_KQlReZpAV2J-g1IHn2TXCrNA5ERRZnFJlvqVc4JxAO8_PEBLxZtB5NbwOYOzN5QhQ6apGf6XsaxGFGhujruzgPIFQ786HC9xnyOTET_DOkDa9UYphkpAWdttvm8E12Xa4MpX7GqzsqzBRsX4hht8T3Hy7Wghw__ITD7U=', 'p_13855271810', 8210149576, 'p_13855271810', 'KimberlyRice', 'free'),
(6572467869, '1BJWap1sBuxgOmfYGdEU0nCgucIfvD4N4yKly1fgT_Pyt8G85cEgrFl5kH6xrtrBcdJ7W71TN1Qm8gVw_VyQmDB8uWFuYRyaovWkKoYT6fAr6pyhvO2trVC3fCjOZRtoSzzunoqqPZtdw9ihJNOeEjDAbRUIoZAnVVuWSV20LkCNK3zT9ofhsphfP4E1B1LJh95fWddw-1mVSAhmd4YDusKx9uvhLFwIJCUJixH6xPLKgKe53nvdQGcEE3IF9uYTpBYRY6DsKh5BhhP_5EeNAJj8VRS1VhXBTYzegPwjp1H7pd97RawvaH_qBss6ZbUmqyeq_bs7jcdtGQIRs9N_HQIJCx3-ysxs=', 'p_967775620746', 6572467869, 'p_967775620746', 'امير العشق', 'free'),
(6587234242, '1BJWap1sBu7MlV3hpF5V8rX7feVITQrHngOjMizxPOzO-muT-3az6QTcV3R21lcgPfVHzcYqL5sbPNlj_IHx8RokOsLthqZs7rlS_7mn7BC2kfzYSYLvCeatHmzwswGjOtiWDkCnjo3-YjO33cq-xpIk7vDUoAtCsIhDXaAc716llcgHimqg6LlopUFrXcXBkznEzcsGD41IqLLxYwz2sFYxjj4dtHXHfXS3NagAtiDRFj_j63Lk46mG09mKTKS60eiQuPxbKYEIDmb0BnFm8LzctDmn_P-s6UWnh9O22xkk_XQ69AZyeA-UgCD8ORdG-vXiVGNZhAF4nwh5wHuxO-WjfXV15o7A=', 'p_967775624389', 6587234242, 'p_967775624389', 'جمالمحمد', 'free'),
(7523947359, '1BJWap1sBu6RlkgM0XafRA-fysZF52z9ZoD9IWKwOOGLeNSJWnljVoukHdLHM_TItfPe0_DkEQ9PqoJTz-nRXGXbKKIbdh6m-j5VP-17vKTtEMAA5BrKz1aD7rpz1Fs4yVypTtAvvtJwHN3UcWmR5fIsIvAvrHysmTXsaiLgs-mOtvg_iuW3Omcf-TmZSjnStedx4NLbKex33DNTwCbziPcFx9bMOToxmKR9Zin8MoJ-85wrBJ9yo4U8af8QmlHIJtaTR18qLCeL1hPe4toEpppGvxTyI7SujZ3k67d6V4aLajeD5bc7Q8QPrViDqJooIWz_yFbD3VKV01nCH4CO7JCKv5X_TkkY=', 'p_967775609261', 7523947359, 'p_967775609261', 'JohnAshley', 'free'),
(8499672561, '1AZWarzQBu6oF15i59jlF7MNBUe6fp2lN2idtq8jK9rkP9hAdXG8J8xL9-t7VAGPGWzsDpOW0OSFqzyIDnts9HwyN__WcQafM-tFGwtzltRm5x1IdX-p5vo6Gt2b3jwRIY2LiMiJhTrpoCyxBponhX9hAaKg3d5sMCOF-50e3gaETl_rRCSVtX0XkhnYI9g-94xU7M063wYuqIlKAmVMDi39cfGQSd9VoDZkiT-94FM8Zy1hlqPsoBIli1MfnxHlOPi7AGSAbEbGzqHt9H-wT0B0jHaOvs0aNrbEVmIxTC1cGIhfprVqO1GKEvazuz5t13Xr0sJb2mdEyKbolTWIoEid5ZsYVvw8=', 'p_13859939226', 8499672561, 'p_13859939226', 'JamieBridges', 'free'),
(7602155227, 'AAH1vlHPD2CiJPfpXuoRooIiNBp-TkHNiZA', 'Luckynyabot', NULL, 'Luckynyabot', '小笼包', 'used');


ALTER TABLE `bot`
  ADD PRIMARY KEY (`bot_id`);
COMMIT;
