写一个 telegram bot
使用 python, aiogram , mysql 
当用户发送消息时，如果是私信，且是媒体，找出这个媒体的file_unqiue_id, 如果是photo,则是使用尺寸最大的为ffile_unqiue_idd
并到 mysql 中，查询此媒体是否有被发布过
依 video, document, photo 三种类型，分别到 table video, document, photo 做查询
若有查到，就说明已经此媒体被发布过了，回复用户“此媒体已发布过”，并将此媒体更新对应的表(video,document,photo)中, 以及 file_extension 中, 
之后再不论 video, document, photo, 都要写到 table sora_content (其中 sora_content.source_id = file_unique_id), 以及 table sora_media 中, 
后结束
若有查到，则回复用户“此媒体未发布过”，并将此媒体新增或更新对应的表(video,document,photo)中, 以及 file_extension 中,
之后再不论 video, document, photo, 都要写到 table sora_content (其中 sora_content.source_id = file_unique_id), 以及 table sora_media 中,

最后再询问用户是否要创建为商品，若用回复按钮“是”，
则在 table product 中新增一条记录，包含商品名称，商品描述，商品价格，商品图片等信息
product.content_id = sora_conetend.id




CREATE TABLE `video` (
  `file_unique_id` varchar(100) NOT NULL,
  `file_size` int(13) UNSIGNED NOT NULL,
  `duration` int(11) NOT NULL,
  `width` int(11) NOT NULL,
  `height` int(11) NOT NULL,
  `file_name` varchar(100) DEFAULT NULL,
  `mime_type` varchar(100) NOT NULL DEFAULT 'video/mp4',
  `caption` mediumtext DEFAULT NULL,
  `create_time` datetime NOT NULL,
  `update_time` datetime DEFAULT NULL,
  `tag_count` int(11) NOT NULL DEFAULT 0,
  `kind` varchar(2) DEFAULT NULL,
  `credit` int(11) DEFAULT 0,
  `files_drive` varchar(100) DEFAULT NULL,
  `root` varchar(50) DEFAULT NULL,
  `kc_id` int(11) UNSIGNED DEFAULT NULL,
  `kc_status` enum('','pending','updated') DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


ALTER TABLE `video`
  ADD PRIMARY KEY (`file_unique_id`),
  ADD KEY `file_size` (`file_size`,`width`,`height`,`mime_type`),
  ADD KEY `file_unique_id` (`file_unique_id`);


CREATE TABLE `document` (
  `file_unique_id` varchar(100) NOT NULL,
  `file_size` int(12) UNSIGNED NOT NULL,
  `file_name` varchar(100) DEFAULT NULL,
  `mime_type` varchar(100) DEFAULT NULL,
  `caption` mediumtext DEFAULT NULL,
  `create_time` datetime NOT NULL,
  `files_drive` varchar(100) DEFAULT NULL,
  `file_password` varchar(150) DEFAULT NULL,
  `kc_id` int(10) UNSIGNED DEFAULT NULL,
  `kc_status` enum('','pending','updated') DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


ALTER TABLE `document`
  ADD PRIMARY KEY (`file_unique_id`),
  ADD KEY `file_unique_id` (`file_unique_id`);


CREATE TABLE `file_extension` (
  `id` int(11) NOT NULL,
  `file_type` enum('document','video','photo','') DEFAULT NULL,
  `file_unique_id` varchar(20) NOT NULL,
  `file_id` varchar(200) NOT NULL,
  `bot` varchar(20) DEFAULT NULL,
  `user_id` varchar(50) DEFAULT NULL,
  `create_time` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

CREATE TABLE `photo` (
  `file_unique_id` varchar(100) NOT NULL,
  `file_size` int(11) NOT NULL,
  `width` int(11) NOT NULL,
  `height` int(11) NOT NULL,
  `file_name` varchar(100) DEFAULT NULL,
  `caption` mediumtext DEFAULT NULL,
  `root_unique_id` varchar(100) DEFAULT NULL,
  `create_time` datetime NOT NULL,
  `files_drive` varchar(100) DEFAULT NULL,
  `hash` varchar(64) DEFAULT NULL,
  `same_fuid` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


ALTER TABLE `photo`
  ADD PRIMARY KEY (`file_unique_id`),
  ADD KEY `file_unique_id` (`file_unique_id`);

ALTER TABLE `file_extension`
  ADD PRIMARY KEY (`id`),
  ADD KEY `file_unique_id` (`file_unique_id`),
  ADD KEY `bot` (`bot`),
  ADD KEY `file_id` (`file_id`),
  ADD KEY `file_unique_id_3` (`file_unique_id`,`file_id`),
  ADD KEY `idx_unique_id_bot` (`file_unique_id`,`bot`);


ALTER TABLE `file_extension`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;


CREATE TABLE `sora_content` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `source_id` varchar(50) NOT NULL,
  `file_type` varchar(10) DEFAULT NULL,
  `content` text DEFAULT NULL,
  `content_seg` text DEFAULT NULL,
  `file_size` bigint(20) UNSIGNED DEFAULT NULL,
  `duration` int(10) UNSIGNED DEFAULT NULL,
  `tag` varchar(200) DEFAULT NULL,
  `thumb_file_unique_id` varchar(100) DEFAULT NULL,
  `thumb_hash` varchar(64) DEFAULT NULL,
  `owner_user_id` bigint(20) UNSIGNED DEFAULT NULL,
  `source_channel_message_id` bigint(20) UNSIGNED DEFAULT NULL,
  `stage` enum('','salai','luguan','no_thumb','no_file','pending','updated','prepare') DEFAULT NULL,
  `plan_update_timestamp` int(13) UNSIGNED DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


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
SET time_zone = "+00:00";

CREATE TABLE `sora_media` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `content_id` bigint(20) UNSIGNED NOT NULL,
  `source_bot_name` varchar(30) NOT NULL,
  `file_id` varchar(150) DEFAULT NULL,
  `thumb_file_id` varchar(150) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


ALTER TABLE `sora_media`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uniq_content_bot` (`content_id`,`source_bot_name`),
  ADD KEY `idx_content_id` (`content_id`);


ALTER TABLE `sora_media`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;


ALTER TABLE `sora_media`
  ADD CONSTRAINT `fk_sora_content` FOREIGN KEY (`content_id`) REFERENCES `sora_content` (`id`) ON DELETE CASCADE;

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

CREATE TABLE `product` (
  `id` bigint(20) NOT NULL COMMENT '商品唯一 ID',
  `name` varchar(255) DEFAULT NULL COMMENT '商品标题，可为空（也可用于展示用途）',
  `content` text DEFAULT NULL COMMENT '商品描述，用于介绍内容或特色',
  `price` int(10) UNSIGNED NOT NULL COMMENT '商品价格，正整数，单位可为积分或金额',
  `content_id` bigint(20) UNSIGNED NOT NULL COMMENT '对应的资源实体 ID，关联 sora_content.id',
  `file_type` varchar(20) DEFAULT NULL COMMENT '商品内容类型，如 video、image、document、collection',
  `owner_user_id` varchar(14) DEFAULT NULL COMMENT '商品投稿者或资源归属用户的 Telegram ID',
  `view_times` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '浏览次数',
  `purchase_times` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '购买次数',
  `like_times` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '点赞次数',
  `dislike_times` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT '点踩次数',
  `hot_score` int(11) NOT NULL DEFAULT 0 COMMENT '热度得分，可正可负，用于排序推荐',
  `bid_status` int(11) NOT NULL DEFAULT 0 COMMENT '投稿状态（例如 0=未投稿, 1=已投稿待审）',
  `review_status` tinyint(3) UNSIGNED NOT NULL DEFAULT 0 COMMENT '审核状态（0=未审，1=通过，2=拒绝等）',
  `purchase_condition` text DEFAULT NULL COMMENT '购买条件（可为 JSON 字符串，如 {"min_points":100}）',
  `created_at` datetime DEFAULT current_timestamp() COMMENT '创建时间',
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT '最后更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='商品主表：用于售卖资源（视频、图片、合集等）';


ALTER TABLE `product`
  ADD PRIMARY KEY (`id`),
  ADD KEY `product_ibfk_1` (`content_id`);


ALTER TABLE `product`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '商品唯一 ID';


ALTER TABLE `product`
  ADD CONSTRAINT `product_ibfk_1` FOREIGN KEY (`content_id`) REFERENCES `sora_content` (`id`);
