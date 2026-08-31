export type Project = {
  id: number
  name: string
  type: "展示类" | "叙事类"
  updated: string
  status: string
}

export type Concept = {
  id: number
  batch: number
  title: string
  strategy: string
  summary: string
  image: string
  tags: string[]
  score: number
  status: "ready" | "generating"
}

export const projects: Project[] = [
  { id: 1, name: "剑侠传奇 · 新版本视觉", type: "展示类", updated: "刚刚", status: "6 套方案" },
  { id: 2, name: "情人节限定时装", type: "展示类", updated: "18 分钟前", status: "生成中" },
  { id: 3, name: "门派恩怨剧情钩子", type: "叙事类", updated: "昨天", status: "已采用" },
  { id: 4, name: "新服预约素材", type: "展示类", updated: "周一", status: "草稿" },
  { id: 5, name: "大侠回归故事线", type: "叙事类", updated: "8 月 26 日", status: "已采用" },
]

export const concepts: Concept[] = [
  {
    id: 1,
    batch: 2,
    title: "一剑开天门",
    strategy: "极端尺度差",
    summary: "巨剑劈开云海与敌阵，用一个瞬间完成力量升级与版本内容量的表达。",
    image: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1400&q=88",
    tags: ["角色主导", "宏大场景", "实力证明"],
    score: 94,
    status: "ready",
  },
  {
    id: 2,
    batch: 2,
    title: "百派争锋录",
    strategy: "门派群像",
    summary: "用并列人物和武器差异承载内容丰度，适合多卖点轮播与版本首曝。",
    image: "https://images.unsplash.com/photo-1511497584788-876760111969?auto=format&fit=crop&w=1400&q=88",
    tags: ["群像", "门派差异", "内容丰度"],
    score: 89,
    status: "ready",
  },
  {
    id: 3,
    batch: 2,
    title: "江湖在掌中",
    strategy: "产品证据",
    summary: "把角色、地图和装备界面折叠成机关式构图，让视觉承诺落到实机证据。",
    image: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=88",
    tags: ["UI 融合", "装备展示", "可玩性"],
    score: 86,
    status: "ready",
  },
  {
    id: 4,
    batch: 1,
    title: "孤城决战",
    strategy: "单点冲突",
    summary: "以孤城和对峙人物构成强冲突，适合剧情悬念型版本预热。",
    image: "https://images.unsplash.com/photo-1473445361085-b9a07f55608b?auto=format&fit=crop&w=1400&q=86",
    tags: ["冲突", "剧情感", "环境叙事"],
    score: 82,
    status: "ready",
  },
  {
    id: 5,
    batch: 1,
    title: "神兵初醒",
    strategy: "装备特写",
    summary: "以材质、纹样和发光细节建立稀有感，卖点集中但内容承载有限。",
    image: "https://images.unsplash.com/photo-1578662996442-48f60103fc96?auto=format&fit=crop&w=1400&q=86",
    tags: ["装备", "材质", "稀有感"],
    score: 79,
    status: "ready",
  },
  {
    id: 6,
    batch: 1,
    title: "山河入画",
    strategy: "世界观奇观",
    summary: "让人物成为世界尺度参照，用大景别展示新区域和探索欲望。",
    image: "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=1400&q=86",
    tags: ["大世界", "探索", "东方奇观"],
    score: 84,
    status: "ready",
  },
]

export const sellingPointOptions = ["新职业登场", "门派对抗", "自由交易", "装备养成", "大世界探索", "新副本"]
export const displayOptions = ["职业技能", "角色立绘", "实机战斗", "装备界面", "门派群像", "世界地图"]
export const styleOptions = ["国风写意", "电影感", "东方奇观", "新中式极简", "厚涂插画", "实机质感"]
