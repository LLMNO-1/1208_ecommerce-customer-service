SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS `commerce`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON `commerce`.* TO 'atguigu'@'%';
FLUSH PRIVILEGES;

USE `commerce`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` VARCHAR(64) NOT NULL UNIQUE,
  `nickname` VARCHAR(100) NOT NULL,
  `level` VARCHAR(32) NOT NULL,
  `mobile_masked` VARCHAR(32) NOT NULL,
  `created_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `products` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `product_id` VARCHAR(64) NOT NULL UNIQUE,
  `title` VARCHAR(255) NOT NULL,
  `description` TEXT NOT NULL,
  `price` DECIMAL(10, 2) NOT NULL,
  `stock_status` VARCHAR(32) NOT NULL,
  `cover_url` VARCHAR(500) NULL,
  `attributes_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `orders` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `order_id` VARCHAR(64) NOT NULL UNIQUE,
  `user_id` BIGINT NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `status_desc` VARCHAR(255) NOT NULL,
  `amount` DECIMAL(10, 2) NOT NULL,
  `created_at` DATETIME NOT NULL,
  `receiver_name` VARCHAR(64) NOT NULL,
  `receiver_phone_masked` VARCHAR(32) NOT NULL,
  `receiver_address` VARCHAR(255) NOT NULL,
  CONSTRAINT `fk_orders_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `order_items` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `order_id` BIGINT NOT NULL,
  `product_id` BIGINT NOT NULL,
  `title_snapshot` VARCHAR(255) NOT NULL,
  `quantity` INT NOT NULL,
  `price` DECIMAL(10, 2) NOT NULL,
  CONSTRAINT `fk_order_items_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `fk_order_items_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `logistics_records` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `order_id` BIGINT NOT NULL,
  `logistics_company` VARCHAR(64) NOT NULL,
  `tracking_number` VARCHAR(64) NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `status_desc` VARCHAR(255) NOT NULL,
  `updated_at` DATETIME NOT NULL,
  CONSTRAINT `fk_logistics_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `logistics_traces` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `logistics_record_id` BIGINT NOT NULL,
  `trace_time` DATETIME NOT NULL,
  `trace_desc` VARCHAR(255) NOT NULL,
  CONSTRAINT `fk_logistics_traces_record` FOREIGN KEY (`logistics_record_id`) REFERENCES `logistics_records` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `refund_requests` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `refund_id` VARCHAR(64) NOT NULL UNIQUE,
  `order_id` BIGINT NOT NULL,
  `operator` VARCHAR(64) NOT NULL,
  `reason` VARCHAR(255) NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `status_desc` VARCHAR(255) NOT NULL,
  `created_at` DATETIME NOT NULL,
  CONSTRAINT `fk_refund_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `shipping_urge_requests` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `urge_id` VARCHAR(64) NOT NULL UNIQUE,
  `order_id` BIGINT NOT NULL,
  `operator` VARCHAR(64) NOT NULL,
  `reason` VARCHAR(255) NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `status_desc` VARCHAR(255) NOT NULL,
  `created_at` DATETIME NOT NULL,
  CONSTRAINT `fk_urge_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `users` (`user_id`, `nickname`, `level`, `mobile_masked`, `created_at`) VALUES
  ('u1001', '小李', 'PLUS', '138****1234', '2026-04-01 09:00:00'),
  ('u1002', '王敏', '普通会员', '139****5678', '2026-04-02 10:30:00'),
  ('u1003', '陈晨', 'PLUS', '137****2468', '2026-04-03 19:20:00');

INSERT INTO `products` (`product_id`, `title`, `description`, `price`, `stock_status`, `cover_url`, `attributes_json`, `created_at`) VALUES
  (
    'SKU10001',
    'iPhone 15 Pro 256G 远峰蓝',
    '6.1 英寸超视网膜 XDR 显示屏，A17 Pro 芯片，支持 5 倍光学变焦。',
    8999.00,
    '有货',
    'https://placehold.co/400x400/0052cc/ffffff?text=iPhone+15+Pro',
    JSON_OBJECT('颜色', '远峰蓝', '容量', '256GB', '屏幕尺寸', '6.1英寸', '网络', '5G'),
    '2026-03-20 12:00:00'
  ),
  (
    'SKU10002',
    '小米恒温电热水壶 3',
    '1.7L 容量，恒温保温，多档温度调节。',
    149.00,
    '有货',
    'https://placehold.co/400x400/ff6a00/ffffff?text=Xiaomi+Kettle',
    JSON_OBJECT('容量', '1.7L', '功率', '1800W', '材质', '304不锈钢'),
    '2026-03-22 14:00:00'
  ),
  (
    'SKU10003',
    '暖火暖宝宝贴 20片装',
    '发热稳定，贴身保暖，适合秋冬日常使用。',
    14.90,
    '有货',
    'https://placehold.co/400x400/e53935/ffffff?text=Warm+Patch',
    JSON_OBJECT('规格', '20片装', '持续时长', '约10小时', '适用部位', '腹部/腰部/背部'),
    '2026-03-25 08:30:00'
  ),
  (
    'SKU10004',
    'Apple Watch Series 9 GPS 45mm',
    '支持全天候视网膜显示屏，健康监测与运动记录。',
    2999.00,
    '有货',
    'https://placehold.co/400x400/333333/ffffff?text=Apple+Watch+S9',
    JSON_OBJECT('颜色', '午夜色', '表壳尺寸', '45mm', '连接方式', 'GPS版'),
    '2026-03-27 11:10:00'
  ),
  (
    'SKU10005',
    '美的空气炸锅 5L',
    '大容量可视窗设计，支持多菜单模式。',
    399.00,
    '有货',
    'https://placehold.co/400x400/009688/ffffff?text=Midea+Airfryer',
    JSON_OBJECT('容量', '5L', '功率', '1500W', '颜色', '奶白色'),
    '2026-03-29 16:20:00'
  ),
  (
    'SKU10006',
    '罗技 MX Master 3S 鼠标',
    '静音微动，支持多设备切换，适合办公与设计。',
    699.00,
    '有货',
    'https://placehold.co/400x400/424242/ffffff?text=MX+Master+3S',
    JSON_OBJECT('颜色', '石墨灰', '连接方式', '蓝牙/USB接收器', '适用系统', 'Windows/macOS'),
    '2026-03-30 13:40:00'
  );

INSERT INTO `orders` (
  `order_id`, `user_id`, `status`, `status_desc`, `amount`, `created_at`, `receiver_name`, `receiver_phone_masked`, `receiver_address`
) VALUES
  (
    'A20260410001',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1001'),
    '待发货',
    '商家正在备货，预计 24 小时内发出。',
    8999.00,
    '2026-04-10 10:00:00',
    '李先生',
    '138****1234',
    '上海市浦东新区世纪大道 100 号'
  ),
  (
    'A20260408002',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1001'),
    '运输中',
    '包裹已发出，正在配送途中。',
    149.00,
    '2026-04-08 15:30:00',
    '李先生',
    '138****1234',
    '上海市浦东新区世纪大道 100 号'
  ),
  (
    'A20260405003',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1001'),
    '已完成',
    '订单已签收完成。',
    14.90,
    '2026-04-05 11:20:00',
    '李先生',
    '138****1234',
    '上海市浦东新区世纪大道 100 号'
  ),
  (
    'A20260407004',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1001'),
    '待揽收',
    '商家已打包完成，正在等待物流揽收。',
    2999.00,
    '2026-04-07 18:15:00',
    '李先生',
    '138****1234',
    '上海市浦东新区世纪大道 100 号'
  ),
  (
    'A20260402005',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1001'),
    '已取消',
    '订单已取消，款项将在 1-3 个工作日内原路退回。',
    399.00,
    '2026-04-02 09:45:00',
    '李先生',
    '138****1234',
    '上海市浦东新区世纪大道 100 号'
  ),
  (
    'B20260409001',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1002'),
    '运输中',
    '包裹正在运输途中，请耐心等待。',
    699.00,
    '2026-04-09 20:30:00',
    '王女士',
    '139****5678',
    '杭州市西湖区文三路 88 号'
  ),
  (
    'B20260401002',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1002'),
    '已完成',
    '订单已签收完成。',
    149.00,
    '2026-04-01 14:05:00',
    '王女士',
    '139****5678',
    '杭州市西湖区文三路 88 号'
  ),
  (
    'C20260406001',
    (SELECT `id` FROM `users` WHERE `user_id` = 'u1003'),
    '待发货',
    '商品正在备货，预计明日发出。',
    399.00,
    '2026-04-06 12:25:00',
    '陈先生',
    '137****2468',
    '北京市朝阳区建国路 56 号'
  );

INSERT INTO `order_items` (`order_id`, `product_id`, `title_snapshot`, `quantity`, `price`) VALUES
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260410001'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10001'),
    'iPhone 15 Pro 256G 远峰蓝',
    1,
    8999.00
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260408002'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10002'),
    '小米恒温电热水壶 3',
    1,
    149.00
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260405003'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10003'),
    '暖火暖宝宝贴 20片装',
    1,
    14.90
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260407004'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10004'),
    'Apple Watch Series 9 GPS 45mm',
    1,
    2999.00
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260402005'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10005'),
    '美的空气炸锅 5L',
    1,
    399.00
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'B20260409001'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10006'),
    '罗技 MX Master 3S 鼠标',
    1,
    699.00
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'B20260401002'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10002'),
    '小米恒温电热水壶 3',
    1,
    149.00
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'C20260406001'),
    (SELECT `id` FROM `products` WHERE `product_id` = 'SKU10005'),
    '美的空气炸锅 5L',
    1,
    399.00
  );

INSERT INTO `logistics_records` (
  `order_id`, `logistics_company`, `tracking_number`, `status`, `status_desc`, `updated_at`
) VALUES
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260408002'),
    '京东物流',
    'JD000123456789',
    '运输中',
    '包裹已到达上海分拨中心，正在安排派送。',
    '2026-04-10 09:00:00'
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260405003'),
    '京东物流',
    'JD000987654321',
    '已签收',
    '您的包裹已签收。',
    '2026-04-06 18:30:00'
  ),
  (
    (SELECT `id` FROM `orders` WHERE `order_id` = 'B20260409001'),
    '顺丰速运',
    'SF0005566778899',
    '派送中',
    '快件已到达派送站点，正在安排派送。',
    '2026-04-11 08:40:00'
  );

INSERT INTO `logistics_traces` (`logistics_record_id`, `trace_time`, `trace_desc`) VALUES
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'JD000123456789'),
    '2026-04-10 09:00:00',
    '包裹已到达上海分拨中心，正在安排派送。'
  ),
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'JD000123456789'),
    '2026-04-09 19:30:00',
    '包裹已从苏州分拨中心发出。'
  ),
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'JD000123456789'),
    '2026-04-09 11:20:00',
    '商家已出库，京东物流已揽收。'
  ),
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'JD000987654321'),
    '2026-04-06 18:30:00',
    '您的包裹已签收。'
  ),
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'JD000987654321'),
    '2026-04-06 10:00:00',
    '配送员已开始派送。'
  ),
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'SF0005566778899'),
    '2026-04-11 08:40:00',
    '快件已到达派送站点，正在安排派送。'
  ),
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'SF0005566778899'),
    '2026-04-10 22:15:00',
    '快件已到达杭州转运中心。'
  ),
  (
    (SELECT `id` FROM `logistics_records` WHERE `tracking_number` = 'SF0005566778899'),
    '2026-04-10 09:20:00',
    '商家已发货，顺丰已揽收。'
  );

INSERT INTO `refund_requests` (
  `refund_id`, `order_id`, `operator`, `reason`, `status`, `status_desc`, `created_at`
) VALUES
  (
    'R202604070001',
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260405003'),
    'system',
    '收到商品后不想要了',
    'completed',
    '退款已完成，款项已原路退回。',
    '2026-04-07 09:30:00'
  ),
  (
    'R202604100002',
    (SELECT `id` FROM `orders` WHERE `order_id` = 'B20260401002'),
    'system',
    '商品有轻微瑕疵',
    'processing',
    '退款申请正在审核中。',
    '2026-04-10 16:20:00'
  );

INSERT INTO `shipping_urge_requests` (
  `urge_id`, `order_id`, `operator`, `reason`, `status`, `status_desc`, `created_at`
) VALUES
  (
    'U202604100001',
    (SELECT `id` FROM `orders` WHERE `order_id` = 'A20260410001'),
    'system',
    '用户希望尽快发货',
    'submitted',
    '发货提醒已创建，商家会尽快处理。',
    '2026-04-10 18:00:00'
  ),
  (
    'U202604070002',
    (SELECT `id` FROM `orders` WHERE `order_id` = 'C20260406001'),
    'system',
    '用户着急使用，希望加快发货',
    'submitted',
    '发货提醒已创建，商家会尽快处理。',
    '2026-04-07 10:15:00'
  );
