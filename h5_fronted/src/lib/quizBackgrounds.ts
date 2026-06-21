/** 35 套小清新背景（对应 35 道题，答完一题切换下一套） */
export type QuizBgTheme = {
  id: number;
  name: string;
  gradient: string;
  blobs: [string, string, string];
};

export const QUESTION_TIME_SEC = 10;

export const QUIZ_BACKGROUNDS: QuizBgTheme[] = [
  { id: 1, name: "晨曦暖橙", gradient: "linear-gradient(145deg, #fef9f2 0%, #fde8d0 45%, #fad4b5 100%)", blobs: ["#fde8d0", "#fef2e6", "#fad4b5"] },
  { id: 2, name: "薰衣草紫", gradient: "linear-gradient(160deg, #faf8fe 0%, #ede4fc 50%, #ddd0f8 100%)", blobs: ["#ede4fc", "#e8ddfa", "#ddd0f8"] },
  { id: 3, name: "樱花初开", gradient: "linear-gradient(135deg, #fefafb 0%, #fceaf2 55%, #f9d8e6 100%)", blobs: ["#fceaf2", "#fce0ec", "#f9d8e6"] },
  { id: 4, name: "薄荷清晨", gradient: "linear-gradient(150deg, #f6fdf9 0%, #d8f5e6 45%, #baeccf 100%)", blobs: ["#def7e8", "#d8f5e6", "#baeccf"] },
  { id: 5, name: "海风轻拂", gradient: "linear-gradient(140deg, #f5fdfe 0%, #d4f4f8 50%, #b8eaf2 100%)", blobs: ["#dff8fb", "#d4f4f8", "#b8eaf2"] },
  { id: 6, name: "金色麦田", gradient: "linear-gradient(155deg, #fefdf7 0%, #faf0c8 48%, #f5e4a0 100%)", blobs: ["#fbf4d8", "#faf0c8", "#f5e4a0"] },
  { id: 7, name: "暮光紫韵", gradient: "linear-gradient(145deg, #fcfafe 0%, #f0e6fc 50%, #e2d0f8 100%)", blobs: ["#f6effc", "#f0e6fc", "#e2d0f8"] },
  { id: 8, name: "奶茶暖棕", gradient: "linear-gradient(150deg, #fbf9f6 0%, #efe3d6 55%, #e2d0c0 100%)", blobs: ["#f5ede4", "#efe3d6", "#e2d0c0"] },
  { id: 9, name: "森林薄雾", gradient: "linear-gradient(140deg, #f5fdf8 0%, #d4f2df 45%, #b8e6c8 100%)", blobs: ["#e0f5e8", "#d4f2df", "#b8e6c8"] },
  { id: 10, name: "玫瑰金辉", gradient: "linear-gradient(155deg, #fefaf5 0%, #fce8d4 50%, #f8d4b0 100%)", blobs: ["#fdf0e4", "#fce8d4", "#f8d4b0"] },
  { id: 11, name: "晴空湛蓝", gradient: "linear-gradient(145deg, #f5f9fe 0%, #d8e8fa 50%, #bdd4f4 100%)", blobs: ["#e4effa", "#d8e8fa", "#bdd4f4"] },
  { id: 12, name: "蜜桃乌龙", gradient: "linear-gradient(150deg, #fefaf6 0%, #fce4e4 45%, #f8ced0 100%)", blobs: ["#fdece8", "#fce4e4", "#f8ced0"] },
  { id: 13, name: "抹茶拿铁", gradient: "linear-gradient(140deg, #f9fdf2 0%, #e6f4c4 50%, #d4eaa5 100%)", blobs: ["#eef8d8", "#e6f4c4", "#d4eaa5"] },
  { id: 14, name: "薄暮珊瑚", gradient: "linear-gradient(155deg, #fef8f8 0%, #fce0e0 48%, #f8cccc 100%)", blobs: ["#fde8e8", "#fce0e0", "#f8cccc"] },
  { id: 15, name: "云雾白桃", gradient: "linear-gradient(145deg, #fefefe 0%, #fcecf4 40%, #f5d0e4 100%)", blobs: ["#fdf4f8", "#fcecf4", "#f5d0e4"] },
  { id: 16, name: "浅海潮汐", gradient: "linear-gradient(150deg, #f5fdfb 0%, #ccf4ec 50%, #a8ece0 100%)", blobs: ["#def8f2", "#ccf4ec", "#a8ece0"] },
  { id: 17, name: "落日余晖", gradient: "linear-gradient(140deg, #fef9f4 0%, #fbdfc0 45%, #f5ccaa 100%)", blobs: ["#fcecd8", "#fbdfc0", "#f5ccaa"] },
  { id: 18, name: "紫藤花开", gradient: "linear-gradient(155deg, #faf8fe 0%, #e0d4f8 50%, #ccbbf4 100%)", blobs: ["#ece4fa", "#e0d4f8", "#ccbbf4"] },
  { id: 19, name: "青柠苏打", gradient: "linear-gradient(145deg, #f9fdf2 0%, #d8f0a8 48%, #c0e680 100%)", blobs: ["#e6f5c4", "#d8f0a8", "#c0e680"] },
  { id: 20, name: "暖绒杏色", gradient: "linear-gradient(150deg, #fefdf7 0%, #faf0c0 40%, #f0e0a0 100%)", blobs: ["#fcf6d8", "#faf0c0", "#f0e0a0"] },
  { id: 21, name: "雾蓝清晨", gradient: "linear-gradient(140deg, #fafbfc 0%, #e8ecf4 50%, #d4dae8 100%)", blobs: ["#f0f2f8", "#e8ecf4", "#d4dae8"] },
  { id: 22, name: "棉花云朵", gradient: "linear-gradient(155deg, #ffffff 0%, #f4f6f9 55%, #e8ecf2 100%)", blobs: ["#fafbfc", "#f4f6f9", "#e8ecf2"] },
  { id: 23, name: "浆果微醺", gradient: "linear-gradient(145deg, #fdf6fe 0%, #f0d4f8 50%, #e0b8f2 100%)", blobs: ["#f8e8fc", "#f0d4f8", "#e0b8f2"] },
  { id: 24, name: "琥珀暖阳", gradient: "linear-gradient(150deg, #fefdf7 0%, #f8e4b0 45%, #f0d48a 100%)", blobs: ["#faf0d0", "#f8e4b0", "#f0d48a"] },
  { id: 25, name: "冰岛蓝湖", gradient: "linear-gradient(140deg, #f5fdfe 0%, #b8f0f4 50%, #90e0e8 100%)", blobs: ["#d4f6f8", "#b8f0f4", "#90e0e8"] },
  { id: 26, name: "春茶新绿", gradient: "linear-gradient(155deg, #f5fdf8 0%, #c0f0d0 48%, #9ae0b4 100%)", blobs: ["#d8f4e4", "#c0f0d0", "#9ae0b4"] },
  { id: 27, name: "藕荷轻纱", gradient: "linear-gradient(145deg, #fdf6fe 0%, #f0d8f8 50%, #e0bcf0 100%)", blobs: ["#f8e8fc", "#f0d8f8", "#e0bcf0"] },
  { id: 28, name: "赤陶晚风", gradient: "linear-gradient(150deg, #fef9f4 0%, #f8dcc0 50%, #f0c8a0 100%)", blobs: ["#fce8d8", "#f8dcc0", "#f0c8a0"] },
  { id: 29, name: "浅湾银沙", gradient: "linear-gradient(140deg, #f5fafe 0%, #d4e8f8 55%, #b8d8f2 100%)", blobs: ["#e4f0fa", "#d4e8f8", "#b8d8f2"] },
  { id: 30, name: "栗色秋意", gradient: "linear-gradient(155deg, #fefdf6 0%, #f8f0b8 40%, #e8d888 100%)", blobs: ["#faf6d0", "#f8f0b8", "#e8d888"] },
  { id: 31, name: "雾紫梦境", gradient: "linear-gradient(145deg, #fcfafe 0%, #e8d8f8 50%, #d4bcf0 100%)", blobs: ["#f4eafc", "#e8d8f8", "#d4bcf0"] },
  { id: 32, name: "晨露青草", gradient: "linear-gradient(150deg, #f5fdf8 0%, #c0eed4 48%, #9ae0bc 100%)", blobs: ["#d8f4e4", "#c0eed4", "#9ae0bc"] },
  { id: 33, name: "粉橙气泡", gradient: "linear-gradient(140deg, #fef9f4 0%, #fce4d4 50%, #f8cecc 100%)", blobs: ["#fdece4", "#fce4d4", "#f8cecc"] },
  { id: 34, name: "静夜星河", gradient: "linear-gradient(155deg, #f6f7fe 0%, #d4d8f8 50%, #bbc0f2 100%)", blobs: ["#e8eafc", "#d4d8f8", "#bbc0f2"] },
  { id: 35, name: "暖灯小窝", gradient: "linear-gradient(145deg, #fef9f4 0%, #faf0c8 45%, #f0e0a0 100%)", blobs: ["#fcf4d8", "#faf0c8", "#f0e0a0"] },
];

export function backgroundForQuestionIndex(answered: number): QuizBgTheme {
  const idx = Math.max(0, Math.min(answered, QUIZ_BACKGROUNDS.length - 1));
  return QUIZ_BACKGROUNDS[idx];
}
