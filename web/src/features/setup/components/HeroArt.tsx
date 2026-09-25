/** 首页横幅背景：月亮、星星、城堡剪影和窗里的烛光（纯装饰） */
export function HeroArt() {
  return (
    <svg
      className="absolute inset-0 size-full"
      viewBox="0 0 1440 260"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
    >
      <circle cx="1180" cy="78" r="44" fill="#F1E8D4" opacity=".92" />
      <circle cx="1198" cy="68" r="40" fill="#111D3F" />
      <g fill="#F1E8D4">
        <circle cx="880" cy="40" r="1.4" opacity=".7" />
        <circle cx="960" cy="92" r="1" opacity=".5" />
        <circle cx="1040" cy="30" r="1.2" opacity=".6" />
        <circle cx="1290" cy="120" r="1" opacity=".5" />
        <circle cx="1340" cy="44" r="1.5" opacity=".8" />
        <circle cx="1100" cy="140" r="1" opacity=".4" />
        <circle cx="760" cy="70" r="1" opacity=".45" />
        <circle cx="1400" cy="96" r="1.1" opacity=".5" />
        <circle cx="420" cy="60" r="1" opacity=".4" />
      </g>
      <path
        fill="#172652"
        d="M0 260V220H80V196H96V220H160V190L180 160L200 190V220H260V170H272V158H284V170H296V158H308V170H320V220H400V200H440V220H520V160L545 120L570 160V220H620V184H700V140L720 100L740 140V184H820V220H880V160L905 124L930 160V220H1000V196H1040V220H1100V174H1112V162H1124V174H1136V162H1148V174H1160V220H1220V190L1240 162L1260 190V220H1340V200H1360V220H1440V260Z"
      />
      <g fill="#D6B25E" opacity=".75">
        <rect x="714" y="150" width="6" height="10" rx="3" />
        <rect x="540" y="176" width="5" height="9" rx="2.5" />
        <rect x="900" y="176" width="5" height="9" rx="2.5" />
        <rect x="176" y="198" width="5" height="8" rx="2.5" />
        <rect x="1236" y="198" width="5" height="8" rx="2.5" />
        <rect x="286" y="186" width="4" height="7" rx="2" />
      </g>
    </svg>
  );
}
