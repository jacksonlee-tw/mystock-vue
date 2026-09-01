// 產業鏈力導向圖（實際是分層固定版面，見下方註解）的 ECharts option 純函式產生器。
//
// 從 IndustryChainView.vue 抽出來的理由：§8 v2.6「圖形互動深度」③放大檢視需要同一份資料
// 在第二個（較大的）畫布重繪；如果版面／配色邏輯只寫在主視圖的 computed 裡，放大檢視只能
// 整段複製貼上一份，兩邊之後很容易改一邊漏改另一邊。抽成純函式後，主視圖與放大檢視 Dialog
// 各自量測自己的容器寬度，呼叫同一個 buildGraphOption() 就能拿到一致的版面與配色。
import { STATE_COLOR, STATE_BG } from '@/utils/industryChainVisuals';

// 分層版面（上游｜中游｜下游），取代純力導向排版——邊一多（例如 CPO 矽光子鏈 63 條）force
// 布局會糊成一坨看不出方向，改成固定欄位＋欄內平均分佈，天生不會互相遮擋。
export const ROLE_COLUMN = { tier2: 0, tier1: 1, downstream: 2 };
export const ROLE_LABEL_POSITION = { tier2: 'left', tier1: 'bottom', downstream: 'right' };
export const PAD_X = 100;   // 左右留白：給欄外標籤（上游靠左、下游靠右）用，太小會被裁掉
export const PAD_Y = 28;
export const ROW_GAP = 64;
export const PULSE_CYCLE_SEC = 1.8;

// 已加入追蹤名單（綠）與已勾選待加入（藍）——刻意都不用既有的狀態色系（棕／橘），
// 免得跟「已突破／低位階候選」的語意混淆。多跳路徑高亮再另用一個藍色系的「追蹤中」色，
// 避免跟「已勾選」的 PICKED 撞色造成誤解（見 HOVER_COLOR）。
const IN_LIST_COLOR = '#059669';
const IN_LIST_BG = '#D1FAE5';
const PICKED_COLOR = '#2563EB';
const PICKED_BG = '#DBEAFE';
const HOVER_COLOR = '#0EA5E9';
const DIMMED_OPACITY = 0.12;

// 量測到的容器寬度反推座標系：節點座標的包圍盒會被 ECharts 縮放到繪圖區，x/y 各自獨立縮放，
// 一旦包圍盒與繪圖區長寬比不同，圓就會被壓成橢圓，因此欄距必須跟著實際寬度反推，讓包圍盒與
// 繪圖區維持 1:1（見主視圖原本的既有註解與教訓）。
export function computeLayoutMetrics(nodes, boxWidth) {
  const byCol = [[], [], []];
  nodes.forEach((n) => byCol[ROLE_COLUMN[n.role] ?? 1].push(n));
  byCol.forEach((col) => col.sort((a, b) => a.symbol.localeCompare(b.symbol)));

  const maxRows = Math.max(1, ...byCol.map((col) => col.length));
  const contentHeight = (maxRows - 1) * ROW_GAP;
  const viewWidth = Math.max(240, (boxWidth || 660) - PAD_X * 2);
  const colGap = viewWidth / 2;

  const posBySymbol = {};
  byCol.forEach((col, colIdx) => {
    const offsetY = ((maxRows - col.length) * ROW_GAP) / 2;
    col.forEach((n, rowIdx) => { posBySymbol[n.symbol] = { x: colIdx * colGap, y: offsetY + rowIdx * ROW_GAP }; });
  });
  return { posBySymbol, contentHeight };
}

export function computeChartHeight(contentHeight) {
  return Math.max(260, contentHeight + PAD_Y * 2);
}

/**
 * @param {object} params
 * @param {Array} params.nodes 圖節點（graphData.nodes）
 * @param {Array} params.edges 圖邊（graphData.edges）
 * @param {number} params.boxWidth 容器實際寬度（由 ResizeObserver 量得）
 * @param {number} [params.pulsePhase] 已突破節點呼吸動畫相位，0~不限，未提供視同 0（無呼吸）
 * @param {(node: object) => boolean} [params.isInWatchlist] 節點是否已在追蹤與觀察名單
 * @param {string[]} [params.selectedSymbols] 已勾選待加入追蹤名單的節點代號
 * @param {{ symbols: Set<string>, edgeKeys: Set<string> } | null} [params.highlighted]
 *   §8 v2.6 ①多跳路徑高亮：hover 節點時由 industryChainGraph.js 的 buildNodeSubgraph() 算出的
 *   完整可達子圖；null 代表目前沒有 hover 任何節點，全部維持正常不透明度。
 * @param {string | null} [params.hoveredSymbol] 目前 hover 中的節點代號，用來給它一個獨立於
 *   「已勾選」「已在名單」之外的強調樣式（藍色系邊框），跟其餘同在路徑上但只是「被連到」的
 *   節點區分開來
 */
export function buildGraphOption({
  nodes,
  edges,
  boxWidth,
  pulsePhase = 0,
  isInWatchlist = () => false,
  selectedSymbols = [],
  highlighted = null,
  hoveredSymbol = null
}) {
  const { posBySymbol, contentHeight } = computeLayoutMetrics(nodes, boxWidth);
  // 0~1 的呼吸強度（sin 正規化），非點火節點固定 0，省得每個節點都各自算一次 sin
  const pulse = (Math.sin((pulsePhase * 2 * Math.PI) / PULSE_CYCLE_SEC) + 1) / 2;

  const echartNodes = nodes.map((n) => {
    const baseSize = n.role === 'downstream' ? 40 : n.role === 'tier1' ? 30 : 22;
    const ignited = n.state === 'ignited';
    const inList = isInWatchlist(n);
    const picked = selectedSymbols.includes(n.symbol);
    const isHovered = hoveredSymbol === n.symbol;
    // 高亮模式下（highlighted 非 null），不在多跳可達子圖內的節點淡出；子圖內的節點（含
    // hover 起點本身）維持原本樣式規則正常顯示，不因為「在高亮模式裡」而改變顏色語意
    const dimmed = highlighted ? !highlighted.symbols.has(n.symbol) : false;
    // 樣式優先序：hover 起點（天藍）＞ 已在名單（綠、不可選）＞ 已勾選（藍框加粗）＞ 點火／一般狀態色
    const borderColor = isHovered ? HOVER_COLOR : inList ? IN_LIST_COLOR : picked ? PICKED_COLOR : (STATE_COLOR[n.state] || STATE_COLOR.dormant);
    const opacity = dimmed ? DIMMED_OPACITY : 1;
    return {
      id: n.symbol,
      name: `${inList ? '✓ ' : ''}${n.symbol} ${n.name}`,
      x: posBySymbol[n.symbol].x,
      y: posBySymbol[n.symbol].y,
      // 已突破節點：大小＋外發光隨 pulse 呼吸（3px／6~20px），視覺上一眼就能跟其餘節點分開；
      // 其餘節點給一圈很淡的陰影做立體感，不然純灰底圓圈在白卡片上會顯得死板扁平
      symbolSize: (ignited ? baseSize + pulse * 6 : baseSize) + (picked || isHovered ? 4 : 0),
      itemStyle: {
        color: inList ? IN_LIST_BG : picked ? PICKED_BG : (STATE_BG[n.state] || STATE_BG.dormant),
        borderColor,
        borderWidth: isHovered ? 4 : picked ? 4 : ignited ? 3 : 2,
        shadowColor: isHovered ? HOVER_COLOR : picked ? PICKED_COLOR : ignited ? STATE_COLOR.ignited : 'rgba(15, 23, 42, 0.12)',
        shadowBlur: isHovered ? 12 : picked ? 10 : ignited ? 6 + pulse * 14 : 5,
        shadowOffsetY: ignited || picked || isHovered ? 0 : 1,
        opacity
      },
      // 分層版面每欄節點是固定座標、垂直平均分佈，不會像力導向那樣互相飄移遮擋，所以三欄
      // 標籤都常駐顯示是安全的
      label: {
        show: true, fontSize: 10, position: ROLE_LABEL_POSITION[n.role] || 'bottom',
        fontWeight: ignited || picked || inList || isHovered ? 'bold' : 'normal',
        color: isHovered ? HOVER_COLOR : inList ? IN_LIST_COLOR : picked ? PICKED_COLOR : ignited ? STATE_COLOR.ignited : undefined,
        opacity,
        formatter: (p) => p.data.name
      }
    };
  });

  // 靜止狀態刻意調淡（opacity 0.45／0.6）——邊一多（CPO 鏈 63 條）全部滿彩實線會很「吵」。
  // 多跳高亮改由這裡手動算好的 opacity／顏色驅動，不再靠 ECharts 內建的 emphasis.focus，
  // 因為 focus:'adjacency' 只做得到單跳，跟本頁要的完整路徑追蹤是兩回事，兩套邏輯同時開
  // 還會互相打架（ECharts 的 blur 狀態會覆蓋掉這裡算好的 itemStyle.opacity）。
  const links = edges.map((e) => {
    const key = `${e.upstream_symbol}->${e.downstream_symbol}`;
    const inPath = highlighted ? highlighted.edgeKeys.has(key) : false;
    const dimmed = highlighted ? !inPath : false;
    return {
      source: e.upstream_symbol,
      target: e.downstream_symbol,
      lineStyle: {
        color: inPath ? HOVER_COLOR : (e.is_verified ? '#79746c' : '#B26A00'),
        type: e.is_verified ? 'solid' : 'dashed',
        width: inPath ? 3 : 1.4,
        opacity: dimmed ? 0.05 : inPath ? 1 : (e.is_verified ? 0.45 : 0.6),
        curveness: 0.15,
        cap: 'round'
      },
      tooltip: { formatter: () => `${e.upstream_symbol} → ${e.downstream_symbol}<br/>${e.component_type || ''}` }
    };
  });

  return {
    contentHeight,
    height: computeChartHeight(contentHeight),
    option: {
      tooltip: {},
      series: [
        {
          type: 'graph',
          layout: 'none',
          roam: true,
          draggable: true,
          cursor: 'pointer',
          // 邊界留白給欄外標籤（上游往左、下游往右），數值與 computeLayoutMetrics 反推欄距時
          // 一致，因此包圍盒與繪圖區等比、縮放 1:1。preserveAspect 是保險：萬一量到的寬度暫時
          // 過期（例如 resize 當下那一幀），ECharts 會改以等比「contain」縮放，圓仍是正圓
          left: PAD_X,
          right: PAD_X,
          top: PAD_Y,
          bottom: PAD_Y,
          preserveAspect: true,
          data: echartNodes,
          links,
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: 6
        }
      ]
    }
  };
}
