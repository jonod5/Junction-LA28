import { View } from 'react-native';
import Svg, { G, Line } from 'react-native-svg';

import { brand } from '@/constants/theme';

interface Props {
  size?: number;
  roadColor?: string;
  laneColor?: string;
}

// Two roads crossing as an X, with dashed lane lines that stop short of the
// intersection. Drawn on a 36-unit grid so it scales cleanly.
export default function JunctionLogo({
  size = 28,
  roadColor = brand.bluebell,
  laneColor = brand.gold,
}: Props) {
  return (
    <View aria-hidden>
      <Svg width={size} height={size} viewBox="0 0 36 36">
        <G stroke={roadColor} strokeWidth={9} strokeLinecap="butt">
          <Line x1={5} y1={5} x2={31} y2={31} />
          <Line x1={31} y1={5} x2={5} y2={31} />
        </G>
        <G
          stroke={laneColor}
          strokeWidth={1.6}
          strokeLinecap="butt"
          strokeDasharray="2.5 2.5"
        >
          <Line x1={6} y1={6} x2={13} y2={13} />
          <Line x1={23} y1={23} x2={30} y2={30} />
          <Line x1={30} y1={6} x2={23} y2={13} />
          <Line x1={13} y1={23} x2={6} y2={30} />
        </G>
      </Svg>
    </View>
  );
}
