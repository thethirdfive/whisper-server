-- ============================================================================
-- whisper-server 预置场景与词库
-- 配套设计文档：whisper-server-design-v0.3.md
--
-- 加载方式：alembic migration 002_seed_scenarios.py 自动加载
-- 也可手动：sqlite3 /data/whisper/db/whisper.db < vocabulary_seed.sql
--
-- 设计目的：
--   1. 转录前自动给 Whisper initial_prompt 提供领域术语提示
--   2. 中英混杂场景识别准确率提升（如"客户"和"customer"互补识别）
--   3. 业务专有名词（GMP、L/C、Interzum 等）避免被识别成普通词
-- ============================================================================

-- 防止重复加载
BEGIN TRANSACTION;

-- ============================================================================
-- 1. 词库 (vocabularies)
-- ============================================================================

INSERT OR IGNORE INTO vocabularies (code, name_zh, name_en, description_zh, description_en, industry, builtin) VALUES
('sales',               '销售管理',     'Sales Management',
 '客户开发、跟进、转化、成交全流程术语',
 'Lead generation, follow-up, conversion, closing terminology',
 'sales', 1),

('general_business',    '通用商务',     'General Business',
 'KPI/OKR/ROI 等跨行业通用商务词汇',
 'Cross-industry business jargon',
 'general', 1),

('exhibition',          '会展行业',     'Exhibition Industry',
 '展位、参展商、主办方、知名展会名等',
 'Booths, exhibitors, organizers, major trade fair names',
 'exhibition', 1),

('health_supplement',   '保健品',       'Health Supplements',
 '营养补充剂、原料、法规、品类术语',
 'Supplements, ingredients, regulations, categories',
 'health', 1),

('international_trade', '国际贸易',     'International Trade',
 '报关、信用证、运输、术语国际通用',
 'Customs, L/C, shipping, Incoterms',
 'trade', 1),

('training',            '培训学习',     'Training & Learning',
 '培训课程、案例、Action Item、复盘相关',
 'Training sessions, cases, action items, retros',
 'training', 1),

('interview',           '访谈研究',     'Interview & Research',
 '客户访谈、用户研究、深度对话术语',
 'Customer interviews, UX research, deep-dive talks',
 'research', 1);


-- ============================================================================
-- 2. 场景 (scenarios)
-- ============================================================================

INSERT OR IGNORE INTO scenarios (code, name_zh, name_en, description_zh, description_en, icon, default_template, builtin, sort_order) VALUES
('internal_meeting',     '内部会议',       'Internal Meeting',
 '团队内部日常会议、周会、月会',
 'Team internal regular meetings, weekly/monthly syncs',
 '🏢', 'minute_docx', 1, 10),

('sales_review',         '销售复盘',       'Sales Review',
 '销售业绩复盘、客户漏斗分析',
 'Sales performance review, pipeline analysis',
 '📊', 'minute_docx', 1, 20),

('customer_interview',   '客户访谈',       'Customer Interview',
 '深度客户访谈、需求挖掘、用户研究',
 'In-depth customer interviews, needs discovery',
 '🎤', 'interview_docx', 1, 30),

('training_session',     '培训课程',       'Training Session',
 '内部/外部培训、知识分享课',
 'Internal/external training, knowledge sharing',
 '📚', 'training_docx', 1, 40),

('customer_visit',       '客户拜访',       'Customer Visit',
 '现场拜访、商务洽谈',
 'Onsite customer visits, business negotiations',
 '🤝', 'minute_docx', 1, 50),

('media_interview',      '媒体采访',       'Media Interview',
 '接受媒体或行业自媒体采访',
 'Being interviewed by media or industry publications',
 '📰', 'interview_docx', 1, 60),

('strategy_discussion',  '战略讨论',       'Strategy Discussion',
 '战略规划、年度计划、季度回顾',
 'Strategic planning, annual/quarterly reviews',
 '🎯', 'minute_docx', 1, 70),

('exhibition_meeting',   '会展业务',       'Exhibition Meeting',
 '会展相关洽谈、参展规划',
 'Exhibition-related discussions and planning',
 '🎪', 'minute_docx', 1, 80),

('health_supplement',    '保健品业务',     'Health Supplement Discussion',
 '保健品研发、采购、合规、营销',
 'Supplement R&D, sourcing, compliance, marketing',
 '💊', 'minute_docx', 1, 90),

('trade_meeting',        '国际贸易',       'International Trade',
 '进出口、报关、物流、信用证',
 'Import/export, customs, logistics, L/C',
 '🚢', 'minute_docx', 1, 100);


-- ============================================================================
-- 3. 场景-词库 多对多关联 (scenario_vocabularies)
-- ============================================================================
-- 每个场景挂载哪些词库

-- internal_meeting → general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'internal_meeting' AND v.code IN ('general_business');

-- sales_review → sales + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'sales_review' AND v.code IN ('sales', 'general_business');

-- customer_interview → interview + sales + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'customer_interview' AND v.code IN ('interview', 'sales', 'general_business');

-- training_session → training + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'training_session' AND v.code IN ('training', 'general_business');

-- customer_visit → sales + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'customer_visit' AND v.code IN ('sales', 'general_business');

-- media_interview → interview + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'media_interview' AND v.code IN ('interview', 'general_business');

-- strategy_discussion → general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'strategy_discussion' AND v.code IN ('general_business');

-- exhibition_meeting → exhibition + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'exhibition_meeting' AND v.code IN ('exhibition', 'general_business');

-- health_supplement → health_supplement + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'health_supplement' AND v.code IN ('health_supplement', 'general_business');

-- trade_meeting → international_trade + general_business
INSERT OR IGNORE INTO scenario_vocabularies (scenario_id, vocabulary_id)
SELECT s.id, v.id FROM scenarios s, vocabularies v
WHERE s.code = 'trade_meeting' AND v.code IN ('international_trade', 'general_business');


-- ============================================================================
-- 4. 销售管理 词库 (sales)
-- ============================================================================

INSERT OR IGNORE INTO vocabulary_terms (vocabulary_id, term_zh, term_en, pinyin, note)
SELECT id, '客户',           'customer',                'kè hù',           '泛指购买方' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '潜在客户',       'prospect',                'qián zài kè hù',  '未成交但有意向' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '意向客户',       'lead',                    'yì xiàng kè hù',  '已表达需求' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '销售漏斗',       'sales funnel',            NULL,              '从触达到成交的流程模型' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '管道',           'pipeline',                NULL,              '在跟进中的客户合集' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '跟进',           'follow up',               'gēn jìn',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '回访',           'follow-up call',          'huí fǎng',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '转化',           'conversion',              'zhuǎn huà',       NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '转化率',         'conversion rate',         'zhuǎn huà lǜ',    NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '成交',           'closing',                 'chéng jiāo',      NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '签单',           'close the deal',          'qiān dān',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '客单价',         'AOV',                     'kè dān jià',      'Average Order Value' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '复购',           'repurchase',              'fù gòu',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '复购率',         'repurchase rate',         NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '客户终身价值',   'LTV',                     NULL,              'Lifetime Value' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '获客成本',       'CAC',                     NULL,              'Customer Acquisition Cost' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '订单',           'order',                   'dìng dān',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '合同',           'contract',                'hé tóng',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '报价',           'quotation',               'bào jià',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '报价单',         'quote',                   'bào jià dān',     NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '议价',           'negotiate',               'yì jià',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '折扣',           'discount',                'zhé kòu',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '回款',           'collection',              'huí kuǎn',        '收回应收款项' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '应收账款',       'accounts receivable',     NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '业绩',           'performance',             'yè jì',           NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '指标',           'target',                  'zhǐ biāo',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '冲刺',           'sprint',                  'chōng cì',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '销售线索',       'sales lead',              NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '线索',           'lead',                    'xiàn suǒ',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '陌拜',           'cold call',               'mò bài',          '陌生拜访' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '电话销售',       'telesales',               NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '上门',           'onsite visit',            'shàng mén',       NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '考察',           'site visit',              'kǎo chá',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '提案',           'proposal',                'tí àn',           NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '方案',           'solution',                'fāng àn',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '决策人',         'decision maker',          'jué cè rén',      NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '决策链',         'decision chain',          NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '关键人',         'key person',              'guān jiàn rén',   NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '需求',           'requirements',            'xū qiú',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '痛点',           'pain point',              'tòng diǎn',       NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '异议',           'objection',               'yì yì',           '客户提出的反对意见' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, 'CRM',            'CRM',                     NULL,              'Customer Relationship Management' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, 'Salesforce',     'Salesforce',              NULL,              '主流 CRM 品牌' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '飞书',           'Feishu / Lark',           'fēi shū',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '钉钉',           'DingTalk',                'dīng dīng',       NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '企业微信',       'WeCom',                   'qǐ yè wēi xìn',   NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '私域',           'private domain traffic',  'sī yù',           NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '公域',           'public traffic',          'gōng yù',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '获客',           'lead acquisition',        'huò kè',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '转介绍',         'referral',                'zhuǎn jiè shào',  NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '老带新',         'referral program',        'lǎo dài xīn',     NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '日报',           'daily report',            'rì bào',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '周报',           'weekly report',           'zhōu bào',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '月报',           'monthly report',          'yuè bào',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '复盘',           'retrospective',           'fù pán',          'review/retro' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '逼单',           'push for closing',        'bī dān',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '促单',           'urge to order',           'cù dān',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '客情',           'customer relationship',   'kè qíng',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '客户画像',       'customer persona',        NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '渠道',           'channel',                 'qú dào',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '代理商',         'agent / distributor',     'dài lǐ shāng',    NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '经销商',         'dealer',                  'jīng xiāo shāng', NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '佣金',           'commission',              'yōng jīn',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '提成',           'commission percentage',   'tí chéng',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '砍价',           'haggle',                  'kǎn jià',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '促销',           'promotion',               'cù xiāo',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '活动',           'campaign',                'huó dòng',        NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '直播',           'livestream',              'zhí bō',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '抖音',           'Douyin',                  'dǒu yīn',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '小红书',         'Xiaohongshu',             'xiǎo hóng shū',   NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '视频号',         'WeChat Channels',         NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '种草',           'product seeding',         'zhòng cǎo',       NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '拔草',           'purchase after seeding',  'bá cǎo',          NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, 'KPI',            'KPI',                     NULL,              'Key Performance Indicator' FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '业绩指标',       'sales target',            NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '末位淘汰',       'last-rank elimination',   NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '出单',           'place an order',          'chū dān',         NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '回款率',         'collection rate',         NULL,              NULL FROM vocabularies WHERE code = 'sales' UNION ALL
SELECT id, '回单',           'order confirmation',      'huí dān',         NULL FROM vocabularies WHERE code = 'sales';


-- ============================================================================
-- 5. 通用商务 词库 (general_business)
-- ============================================================================

INSERT OR IGNORE INTO vocabulary_terms (vocabulary_id, term_zh, term_en, pinyin, note)
SELECT id, NULL,             'KPI',                     NULL,             'Key Performance Indicator' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'OKR',                     NULL,             'Objectives and Key Results' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'ROI',                     NULL,             'Return on Investment' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'ROAS',                    NULL,             'Return on Ad Spend' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'GMV',                     NULL,             'Gross Merchandise Value' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'P&L',                     NULL,             'Profit and Loss' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'EBITDA',                  NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'YoY',                     NULL,             'Year over Year' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'MoM',                     NULL,             'Month over Month' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'QoQ',                     NULL,             'Quarter over Quarter' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'B2B',                     NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'B2C',                     NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'B2B2C',                   NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'SaaS',                    NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'PaaS',                    NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'IaaS',                    NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'MVP',                     NULL,             'Minimum Viable Product' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, NULL,             'PMF',                     NULL,             'Product Market Fit' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '战略',           'strategy',                'zhàn lüè',       NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '战术',           'tactics',                 'zhàn shù',       NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '商业模式',       'business model',          NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '盈利模式',       'profit model',            NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '现金流',         'cash flow',               'xiàn jīn liú',   NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '毛利',           'gross profit',            'máo lì',         NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '毛利率',         'gross margin',            'máo lì lǜ',      NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '净利',           'net profit',              'jìng lì',        NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '营收',           'revenue',                 'yíng shōu',      NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '成本',           'cost',                    'chéng běn',      NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '运营',           'operations',              'yùn yíng',       NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '增长',           'growth',                  'zēng zhǎng',     NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '裂变',           'viral growth',            'liè biàn',       NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '用户留存',       'retention',               NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '活跃用户',       'active users',            NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'DAU',            'DAU',                     NULL,             'Daily Active Users' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'MAU',            'MAU',                     NULL,             'Monthly Active Users' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'ARR',            'ARR',                     NULL,             'Annual Recurring Revenue' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'MRR',            'MRR',                     NULL,             'Monthly Recurring Revenue' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '股权',           'equity',                  'gǔ quán',        NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '融资',           'fundraising',             'róng zī',        NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '天使轮',         'angel round',             'tiān shǐ lún',   NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'A 轮',           'Series A',                NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'IPO',            'IPO',                     NULL,             'Initial Public Offering' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '股东',           'shareholder',             'gǔ dōng',        NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '董事会',         'board of directors',      'dǒng shì huì',   NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'CEO',            'CEO',                     NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'COO',            'COO',                     NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'CFO',            'CFO',                     NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, 'CTO',            'CTO',                     NULL,             NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '副总',           'VP',                      'fù zǒng',        '副总裁' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '总监',           'director',                'zǒng jiān',      NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '经理',           'manager',                 'jīng lǐ',        NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '主管',           'supervisor',              'zhǔ guǎn',       NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '招聘',           'recruiting',              'zhāo pìn',       NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '入职',           'onboarding',              'rù zhí',         NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '离职',           'resignation',             'lí zhí',         NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '裁员',           'layoff',                  'cái yuán',       NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '绩效',           'performance',             'jì xiào',        NULL FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '股权激励',       'equity incentive',        NULL,             'ESOP' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '安博沃康',       'Ambowokang',              'ān bó wò kāng',  '公司名' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '点书科技',       'Dianshu Tech',            'diǎn shū',       '公司名' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '那格会展',       'Naghe Expo',              'nà gé',          '公司名' FROM vocabularies WHERE code = 'general_business' UNION ALL
SELECT id, '香港公司',       'HK entity',               'xiāng gǎng',     NULL FROM vocabularies WHERE code = 'general_business';


-- ============================================================================
-- 6. 会展行业 词库 (exhibition)
-- ============================================================================

INSERT OR IGNORE INTO vocabulary_terms (vocabulary_id, term_zh, term_en, pinyin, note)
SELECT id, '展位',           'booth',                   'zhǎn wèi',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '标摊',           'standard booth',          'biāo tān',       '标准展位 9㎡' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '光地',           'raw space',               'guāng dì',       '只占面积自行搭建' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '搭建',           'booth construction',      'dā jiàn',        NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '展览',           'exhibition',              'zhǎn lǎn',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '展会',           'trade fair',              'zhǎn huì',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '展商',           'exhibitor',               'zhǎn shāng',     NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '参展商',         'exhibitor',               'cān zhǎn shāng', NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '观众',           'visitor',                 'guān zhòng',     '专业观众' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '采购商',         'buyer',                   'cǎi gòu shāng',  NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '主办方',         'organizer',               'zhǔ bàn fāng',   NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '承办方',         'co-organizer',            'chéng bàn fāng', NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '协办',           'co-sponsor',              'xié bàn',        NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '展馆',           'exhibition hall',         'zhǎn guǎn',      NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '展厅',           'pavilion',                'zhǎn tīng',      NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '中国馆',         'China Pavilion',          NULL,             NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '主通道',         'main aisle',              NULL,             NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '双开',           'corner booth',            'shuāng kāi',     '两面开口的展位' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '岛屿',           'island booth',            'dǎo yǔ',         '四面开口' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '会刊',           'show catalog',            'huì kān',        NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '邀请函',         'invitation',              'yāo qǐng hán',   NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '签证',           'visa',                    'qiān zhèng',     NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '申根签',         'Schengen visa',           NULL,             NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '团签',           'group visa',              'tuán qiān',      NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '商务签',         'business visa',           NULL,             NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '观展',           'visit the fair',          'guān zhǎn',      NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '观展团',         'visiting delegation',     NULL,             NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '参展团',         'exhibitor delegation',    NULL,             NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '布展',           'move-in',                 'bù zhǎn',        NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '撤展',           'move-out',                'chè zhǎn',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '展期',           'show dates',              'zhǎn qī',        NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '补贴',           'subsidy',                 'bǔ tiē',         '政府/协会补贴' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '展位图',         'floor plan',              'zhǎn wèi tú',    NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '选位',           'booth selection',         'xuǎn wèi',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '订位',           'book a booth',            'dìng wèi',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '定金',           'deposit',                 'dìng jīn',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '尾款',           'final payment',           'wěi kuǎn',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '领队',           'tour leader',             'lǐng duì',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '团员',           'delegation member',       'tuán yuán',      NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '单房差',         'single room supplement',  'dān fáng chā',   NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
-- 知名展会
SELECT id, NULL,             'Interzum',                NULL,             '德国科隆木工五金展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'Intermob',                NULL,             '土耳其伊斯坦布尔家具配件展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'Ligna',                   NULL,             '德国汉诺威木工机械展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'IBS',                     NULL,             '国际建材展 / International Builders'' Show' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'IWF',                     NULL,             '美国亚特兰大国际木工展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'IMM Cologne',             NULL,             '德国科隆家具展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'Big 5',                   NULL,             '迪拜五大行业建材展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'Mable',                   NULL,             '俄罗斯莫斯科家具展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'Woodex',                  NULL,             '俄罗斯木工机械展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, NULL,             'KIOFF',                   NULL,             '韩国家具展' FROM vocabularies WHERE code = 'exhibition' UNION ALL
-- 地点
SELECT id, '汉诺威',         'Hannover',                'hàn nuò wēi',    '德国' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '科隆',           'Cologne',                 'kē lóng',        '德国' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '伊斯坦布尔',     'Istanbul',                'yī sī tǎn bù ěr','土耳其' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '哈萨克斯坦',     'Kazakhstan',              'hā sà kè sī tǎn',NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '哈萨克',         'Kazakh',                  'hā sà kè',       '哈萨克斯坦简称' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '阿斯塔纳',       'Astana',                  'ā sī tǎ nà',     '哈萨克首都' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '迪拜',           'Dubai',                   'dí bài',         NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '雅加达',         'Jakarta',                 'yǎ jiā dá',      '印尼' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '吉达',           'Jeddah',                  'jí dá',          '沙特' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '利雅得',         'Riyadh',                  'lì yǎ dé',       '沙特首都' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '拉斯维加斯',     'Las Vegas',               NULL,             NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '亚特兰大',       'Atlanta',                 'yà tè lán dà',   NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '河内',           'Hanoi',                   'hé nèi',         '越南' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '胡志明',         'Ho Chi Minh',             'hú zhì míng',    '越南' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '吉隆坡',         'Kuala Lumpur',            'jí lóng pō',     '马来西亚' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '曼谷',           'Bangkok',                 'màn gǔ',         '泰国' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '广州',           'Guangzhou',               'guǎng zhōu',     NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '深圳',           'Shenzhen',                'shēn zhèn',      NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '青岛',           'Qingdao',                 'qīng dǎo',       NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '济南',           'Jinan',                   'jǐ nán',         NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '常州',           'Changzhou',               'cháng zhōu',     NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '佛山',           'Foshan',                  'fó shān',        NULL FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '中外运',         'Sinotrans',               NULL,             '物流公司' FROM vocabularies WHERE code = 'exhibition' UNION ALL
SELECT id, '中银',           'Sinotrans Expo',          NULL,             '会展同行' FROM vocabularies WHERE code = 'exhibition';


-- ============================================================================
-- 7. 保健品 词库 (health_supplement)
-- ============================================================================

INSERT OR IGNORE INTO vocabulary_terms (vocabulary_id, term_zh, term_en, pinyin, note)
SELECT id, '保健品',         'health supplement',       'bǎo jiàn pǐn',   NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '膳食补充剂',     'dietary supplement',      NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '益生菌',         'probiotics',              'yì shēng jūn',   NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '益生元',         'prebiotics',              'yì shēng yuán',  NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '后生元',         'postbiotics',             'hòu shēng yuán', NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '膳食纤维',       'dietary fiber',           NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '维生素',         'vitamin',                 'wéi shēng sù',   NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '矿物质',         'mineral',                 'kuàng wù zhì',   NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '叶黄素',         'lutein',                  'yè huáng sù',    NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '辅酶 Q10',       'CoQ10',                   NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '鱼油',           'fish oil',                'yú yóu',         NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'DHA',            'DHA',                     NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'EPA',            'EPA',                     NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '葡萄籽',         'grape seed extract',      'pú táo zǐ',      NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '蓝莓',           'blueberry',               'lán méi',        NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '螺旋藻',         'spirulina',               'luó xuán zǎo',   NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '蛋白粉',         'protein powder',          'dàn bái fěn',    NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '乳清蛋白',       'whey protein',            NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '胶原蛋白',       'collagen',                NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '玻尿酸',         'hyaluronic acid',         'bō niào suān',   NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '钙片',           'calcium tablet',          'gài piàn',       NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '复合维生素',     'multivitamin',            NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '功能性食品',     'functional food',         NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '保健功效',       'health claim',            NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '剂型',           'dosage form',             'jì xíng',        NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '软糖',           'gummy',                   'ruǎn táng',      NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '胶囊',           'capsule',                 'jiāo náng',      NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '片剂',           'tablet',                  'piàn jì',        NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '液体',           'liquid',                  'yè tǐ',          NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '粉剂',           'powder',                  'fěn jì',         NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '蓝帽子',         'Blue Hat',                'lán mào zi',     '中国保健食品标识' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '保健食品',       'health food (regulated)', NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
-- 法规
SELECT id, 'GMP',            'GMP',                     NULL,             'Good Manufacturing Practice' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'FDA',            'FDA',                     NULL,             '美国食品药品监督管理局' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'NSF',            'NSF',                     NULL,             '美国国家卫生基金会' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'HACCP',          'HACCP',                   NULL,             '危害分析关键控制点' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'ISO 22000',      'ISO 22000',               NULL,             '食品安全管理' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '蓝帽认证',       'Blue Hat certification',  NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '备案',           'registration',            'bèi àn',         '保健食品备案' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '注册',           'registration approval',   'zhù cè',         NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
-- 营销
SELECT id, '品牌方',         'brand owner',             'pǐn pái fāng',   NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '代工厂',         'OEM factory',             'dài gōng chǎng', NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'OEM',            'OEM',                     NULL,             'Original Equipment Manufacturer' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, 'ODM',            'ODM',                     NULL,             'Original Design Manufacturer' FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '原料',           'raw material',            'yuán liào',      NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '辅料',           'excipient',               'fǔ liào',        NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '配方',           'formula',                 'pèi fāng',       NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '配比',           'ratio',                   'pèi bǐ',         NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '小红书种草',     'Xiaohongshu seeding',     NULL,             NULL FROM vocabularies WHERE code = 'health_supplement' UNION ALL
SELECT id, '跨境电商',       'cross-border e-commerce', NULL,             NULL FROM vocabularies WHERE code = 'health_supplement';


-- ============================================================================
-- 8. 国际贸易 词库 (international_trade)
-- ============================================================================

INSERT OR IGNORE INTO vocabulary_terms (vocabulary_id, term_zh, term_en, pinyin, note)
SELECT id, '进出口',         'import-export',           'jìn chū kǒu',    NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '出口',           'export',                  'chū kǒu',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '进口',           'import',                  'jìn kǒu',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '报关',           'customs declaration',     'bào guān',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '清关',           'customs clearance',       'qīng guān',      NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '关税',           'tariff',                  'guān shuì',      NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '增值税',         'VAT',                     'zēng zhí shuì',  'Value Added Tax' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '退税',           'tax rebate',              'tuì shuì',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '海关',           'customs',                 'hǎi guān',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '商检',           'commodity inspection',    'shāng jiǎn',     NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '原产地证',       'certificate of origin',   NULL,             NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'HS Code',        'HS Code',                 NULL,             '商品编码' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '海运',           'sea freight',             'hǎi yùn',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '空运',           'air freight',             'kōng yùn',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '陆运',           'land freight',            'lù yùn',         NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '铁运',           'rail freight',            'tiě yùn',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '集装箱',         'container',               'jí zhuāng xiāng',NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '货柜',           'shipping container',      'huò guì',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '整柜',           'FCL',                     'zhěng guì',      'Full Container Load' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '拼柜',           'LCL',                     'pīn guì',        'Less than Container Load' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'FCL',            'FCL',                     NULL,             'Full Container Load' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'LCL',            'LCL',                     NULL,             'Less than Container Load' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '提单',           'B/L',                     'tí dān',         'Bill of Lading' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '装箱单',         'packing list',            'zhuāng xiāng dān',NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '商业发票',       'commercial invoice',      NULL,             NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '信用证',         'L/C',                     'xìn yòng zhèng', 'Letter of Credit' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'L/C',            'L/C',                     NULL,             'Letter of Credit' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'TT',             'T/T',                     NULL,             'Telegraphic Transfer' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'DP',             'D/P',                     NULL,             'Documents against Payment' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'DA',             'D/A',                     NULL,             'Documents against Acceptance' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'OA',             'O/A',                     NULL,             'Open Account' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '电汇',           'wire transfer',           'diàn huì',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '汇款',           'remittance',              'huì kuǎn',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '汇率',           'exchange rate',           'huì lǜ',         NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '美元',           'USD',                     'měi yuán',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '欧元',           'EUR',                     'ōu yuán',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '人民币',         'RMB',                     'rén mín bì',     NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '港币',           'HKD',                     'gǎng bì',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'Incoterms',      'Incoterms',               NULL,             '国际贸易术语' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'FOB',            'FOB',                     NULL,             'Free On Board' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'CIF',            'CIF',                     NULL,             'Cost, Insurance & Freight' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'CFR',            'CFR',                     NULL,             'Cost and Freight' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'EXW',            'EXW',                     NULL,             'Ex Works' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, 'DDP',            'DDP',                     NULL,             'Delivered Duty Paid' FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '货代',           'freight forwarder',       'huò dài',        NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '船公司',         'shipping line',           'chuán gōng sī',  NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '船期',           'shipping schedule',       'chuán qī',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '港口',           'port',                    'gǎng kǒu',       NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '上海港',         'Port of Shanghai',        NULL,             NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '宁波港',         'Port of Ningbo',          NULL,             NULL FROM vocabularies WHERE code = 'international_trade' UNION ALL
SELECT id, '温州港',         'Port of Wenzhou',         NULL,             NULL FROM vocabularies WHERE code = 'international_trade';


-- ============================================================================
-- 9. 培训学习 词库 (training)
-- ============================================================================

INSERT OR IGNORE INTO vocabulary_terms (vocabulary_id, term_zh, term_en, pinyin, note)
SELECT id, '讲师',           'instructor',              'jiǎng shī',      NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '导师',           'mentor',                  'dǎo shī',        NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '学员',           'trainee',                 'xué yuán',       NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '助教',           'TA',                      'zhù jiào',       'Teaching Assistant' FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '课程大纲',       'syllabus',                NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '案例分析',       'case study',              NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '情景模拟',       'role play',               NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '小组讨论',       'group discussion',        NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '头脑风暴',       'brainstorming',           'tóu nǎo fēng bào',NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '提问',           'Q&A',                     'tí wèn',         NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '答疑',           'Q&A',                     'dá yí',          NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '互动',           'interaction',             'hù dòng',        NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '演练',           'drill',                   'yǎn liàn',       NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '考试',           'exam',                    'kǎo shì',        NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '考核',           'assessment',              'kǎo hé',         NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '证书',           'certificate',             'zhèng shū',      NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '复盘',           'retrospective',           'fù pán',         NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '总结',           'summary',                 'zǒng jié',       NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '行动项',         'action item',             'xíng dòng xiàng',NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '负责人',         'owner',                   'fù zé rén',      NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '截止日期',       'deadline',                'jié zhǐ rì qī',  NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, 'Action Item',    'Action Item',             NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, 'Takeaway',       'Takeaway',                NULL,             '关键收获' FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, 'Workshop',       'Workshop',                NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, 'Bootcamp',       'Bootcamp',                NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, 'Onboarding',     'Onboarding',              NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '入职培训',       'onboarding training',     NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '岗前培训',       'pre-service training',    'gǎng qián',      NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '在岗培训',       'on-the-job training',     NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '管理培训',       'management training',     NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '销售培训',       'sales training',          NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '团建',           'team building',           'tuán jiàn',      NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '述职',           'self-review',             'shù zhí',        NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '分享',           'share',                   'fēn xiǎng',      NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '复训',           'refresher training',      'fù xùn',         NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '知识体系',       'knowledge system',        NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '能力模型',       'competency model',        NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '第一性原理',     'first principles',        NULL,             NULL FROM vocabularies WHERE code = 'training' UNION ALL
SELECT id, '心智模式',       'mental model',            'xīn zhì mó shì', NULL FROM vocabularies WHERE code = 'training';


-- ============================================================================
-- 10. 访谈研究 词库 (interview)
-- ============================================================================

INSERT OR IGNORE INTO vocabulary_terms (vocabulary_id, term_zh, term_en, pinyin, note)
SELECT id, '访谈',           'interview',               'fǎng tán',       NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '受访者',         'interviewee',             'shòu fǎng zhě',  NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '访谈者',         'interviewer',             'fǎng tán zhě',   NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '深度访谈',       'in-depth interview',      NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '焦点小组',       'focus group',             NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '半结构化',       'semi-structured',         NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '提纲',           'outline',                 'tí gāng',        NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '开放问题',       'open-ended question',     NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '封闭问题',       'closed question',         NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '关键洞察',       'key insight',             NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '洞察',           'insight',                 'dòng chá',       NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '痛点',           'pain point',              'tòng diǎn',      NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '需求',           'need',                    'xū qiú',         NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '动机',           'motivation',              'dòng jī',        NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '行为',           'behavior',                'xíng wéi',       NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '态度',           'attitude',                'tài dù',         NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '用户画像',       'persona',                 NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '用户旅程',       'customer journey',        NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, 'Pain Point',     'Pain Point',              NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, 'Use Case',       'Use Case',                NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, 'Customer Journey','Customer Journey',       NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, 'Jobs to be Done', 'Jobs to be Done',        NULL,             'JTBD 用户任务理论' FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, 'JTBD',           'JTBD',                    NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '5 Why',          '5 Why',                   NULL,             '追问 5 次为什么' FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '记录员',         'note taker',              'jì lù yuán',     NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '逐字稿',         'verbatim transcript',     'zhú zì gǎo',     NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '主题分析',       'thematic analysis',       NULL,             NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '亲和图',         'affinity diagram',        'qīn hé tú',      NULL FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '编码',           'coding',                  'biān mǎ',        '定性研究的编码' FROM vocabularies WHERE code = 'interview' UNION ALL
SELECT id, '饱和',           'saturation',              'bǎo hé',         '访谈饱和度' FROM vocabularies WHERE code = 'interview';


COMMIT;

-- ============================================================================
-- 校验
-- ============================================================================
-- SELECT v.code, COUNT(vt.id) AS term_count
-- FROM vocabularies v
-- LEFT JOIN vocabulary_terms vt ON vt.vocabulary_id = v.id
-- GROUP BY v.id ORDER BY v.id;

-- 预期输出：
-- sales              | 80 (左右)
-- general_business   | 62
-- exhibition         | 76
-- health_supplement  | 50
-- international_trade| 51
-- training           | 39
-- interview          | 30
-- 总计 ~388 个词条
