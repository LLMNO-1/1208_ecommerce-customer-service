SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS `customer_service`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON `customer_service`.* TO 'atguigu'@'%';
FLUSH PRIVILEGES;

USE `customer_service`;

CREATE TABLE IF NOT EXISTS `dialogue_states` (
  `sender_id` VARCHAR(255) NOT NULL COMMENT '用户唯一标识',
  `state_json` TEXT NOT NULL COMMENT '完整对话状态 JSON',
  PRIMARY KEY (`sender_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
