export const labs = [
  {
    id: 1,
    name: '人工智能实验室',
    capacity: 30,
    openTime: '周一至周五 08:00-22:00',
    rule: '需提前一天预约；使用 GPU 设备须登记；实验室内禁止饮食。',
    description: '面向深度学习、计算机视觉方向的教学与科研实验。',
    deviceIds: [1, 2, 3]
  },
  {
    id: 2,
    name: '机器人实验室',
    capacity: 20,
    openTime: '周一至周六 09:00-21:00',
    rule: '机械臂操作须两人在场；设备使用后需归位并登记状态。',
    description: '面向机器人控制、运动规划与具身智能实验。',
    deviceIds: [4, 5, 6]
  },
  {
    id: 3,
    name: '云计算实验室',
    capacity: 40,
    openTime: '每天 08:00-23:00',
    rule: '服务器资源按课程优先级分配；禁止擅自更改网络配置。',
    description: '面向云计算、容器与分布式系统实验。',
    deviceIds: [7, 8]
  },
  {
    id: 4,
    name: '软件工程实验室',
    capacity: 50,
    openTime: '周一至周五 08:00-22:30',
    rule: '小组预约需注明项目名称；离场前关闭投影与空调。',
    description: '面向软件项目开发、测试与答辩演练。',
    deviceIds: [9, 10]
  }
]

export const devices = [
  { id: 1, name: 'GPU 服务器', labId: 1, model: 'NVIDIA A100 × 4', count: 2, status: '正常' },
  { id: 2, name: '深度学习工作站', labId: 1, model: 'RTX 4090', count: 4, status: '正常' },
  { id: 3, name: '高性能 PC', labId: 1, model: 'i9 / 64G', count: 10, status: '正常' },
  { id: 4, name: '六轴机械臂', labId: 2, model: 'UR5', count: 2, status: '维护中' },
  { id: 5, name: '移动机器人', labId: 2, model: 'TurtleBot4', count: 4, status: '正常' },
  { id: 6, name: '3D 打印机', labId: 2, model: 'Raise3D Pro3', count: 1, status: '正常' },
  { id: 7, name: '服务器机柜', labId: 3, model: 'Dell R750 × 8', count: 4, status: '正常' },
  { id: 8, name: '云终端', labId: 3, model: '瘦客户端', count: 40, status: '正常' },
  { id: 9, name: '一体机', labId: 4, model: 'i7 / 32G', count: 50, status: '正常' },
  { id: 10, name: '投影设备', labId: 4, model: 'Epson CB-700U', count: 2, status: '正常' }
]

export const bookings = [
  {
    id: 'BK20261104001',
    labId: 1,
    labName: '人工智能实验室',
    date: '2026-11-05',
    start: '14:00',
    end: '16:00',
    people: 6,
    type: '小组',
    devices: ['GPU 服务器', '深度学习工作站'],
    purpose: '课程项目模型训练',
    status: 'pending',
    reason: '',
    applicant: '张同学',
    hoursUntilStart: 20
  },
  {
    id: 'BK20261104002',
    labId: 2,
    labName: '机器人实验室',
    date: '2026-11-05',
    start: '09:00',
    end: '11:00',
    people: 4,
    type: '小组',
    devices: ['六轴机械臂'],
    purpose: '机械臂抓取实验',
    status: 'conflict',
    reason: '与 BK20261104005（机器人实验室 11-05 09:30–11:30，李同学）时段重叠，等待管理员决定保留哪一单',
    applicant: '李同学',
    hoursUntilStart: 15
  },
  {
    id: 'BK20261104003',
    labId: 3,
    labName: '云计算实验室',
    date: '2026-11-06',
    start: '19:00',
    end: '21:00',
    people: 30,
    type: '班级',
    devices: ['云终端'],
    purpose: '容器编排课程实验',
    status: 'approved',
    reason: '',
    applicant: '王同学',
    hoursUntilStart: 30
  },
  {
    id: 'BK20261104004',
    labId: 4,
    labName: '软件工程实验室',
    date: '2026-11-05',
    start: '08:00',
    end: '10:00',
    people: 55,
    type: '班级',
    devices: ['一体机'],
    purpose: '项目答辩演练',
    status: 'rejected',
    reason: '人数超过实验室容纳上限（50 人），请调整后重新提交',
    applicant: '赵同学',
    hoursUntilStart: 14
  },
  {
    id: 'BK20261104005',
    labId: 2,
    labName: '机器人实验室',
    date: '2026-11-05',
    start: '09:30',
    end: '11:30',
    people: 3,
    type: '小组',
    devices: ['移动机器人'],
    purpose: '导航算法测试',
    status: 'pending',
    reason: '',
    applicant: '陈同学',
    hoursUntilStart: 15
  },
  {
    id: 'BK20261104006',
    labId: 1,
    labName: '人工智能实验室',
    date: '2026-11-07',
    start: '10:00',
    end: '12:00',
    people: 2,
    type: '个人',
    devices: ['高性能 PC'],
    purpose: '论文复现',
    status: 'cancelled',
    reason: '学生主动取消',
    applicant: '张同学',
    hoursUntilStart: 50
  }
]

export const users = [
  { id: 1, name: '张同学', role: '学生', account: 'stu_zhang', phone: '138****0001', status: '正常' },
  { id: 2, name: '李同学', role: '学生', account: 'stu_li', phone: '138****0002', status: '正常' },
  { id: 3, name: '王老师', role: '教师', account: 'tea_wang', phone: '139****0003', status: '正常' },
  { id: 4, name: '陈管理员', role: '管理员', account: 'admin_chen', phone: '137****0004', status: '正常' },
  { id: 5, name: '刘同学', role: '学生', account: 'stu_liu', phone: '138****0005', status: '停用' }
]

export const notices = [
  { id: 1, title: '有 2 条预约待审核', time: '10 分钟前', read: false },
  { id: 2, title: '机器人实验室 09:00-11:00 出现时间冲突', time: '25 分钟前', read: false },
  { id: 3, title: '王同学申请取消 11 月 6 日的预约', time: '1 小时前', read: true }
]
