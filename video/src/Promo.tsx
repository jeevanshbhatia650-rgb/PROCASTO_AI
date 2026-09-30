import { Audio } from "@remotion/media";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Fragment } from "react";
import { AbsoluteFill, interpolate, staticFile } from "remotion";
import { Answer, Alert, Home, Speed, Voice } from "./scenes/Product";
import { Connect, Follow } from "./scenes/Connect";
import { Data, Different, End } from "./scenes/Closing";
import { Hook, Problem, Reveal } from "./scenes/Intro";

export const FPS = 30;
export const FADE = 12;

// The music: "lo-fi beat" by zephiramusic, 76 BPM, first beat at 0.093 s (measured from the file).
const BEAT = (FPS * 60) / 76;
const FIRST_BEAT = 0.093 * FPS;
const onBeat = (frame: number) => Math.round(FIRST_BEAT + Math.round((frame - FIRST_BEAT) / BEAT) * BEAT);

/** The film in order, with roughly how long each scene wants. Cuts are then moved onto the nearest beat. */
const PLAN = [
  { id: "Hook", component: Hook, duration: 150 },
  { id: "Problem", component: Problem, duration: 110 },
  { id: "Reveal", component: Reveal, duration: 134 }, // sits in the song's quiet break
  { id: "Connect", component: Connect, duration: 420 }, // lands where the drums come back
  { id: "Follow", component: Follow, duration: 210 },
  { id: "Home", component: Home, duration: 270 },
  { id: "Alert", component: Alert, duration: 220 },
  { id: "Answer", component: Answer, duration: 320 },
  { id: "Data", component: Data, duration: 300 },
  { id: "Speed", component: Speed, duration: 250 },
  { id: "Voice", component: Voice, duration: 150 },
  { id: "Different", component: Different, duration: 190 },
  { id: "End", component: End, duration: 180 },
] as const;

// Where each cut would fall, snapped to the beat; a scene then lasts until the next cut plus the crossfade.
const cuts = PLAN.reduce<number[]>((at, s, i) => [...at, i === 0 ? 0 : onBeat(at[i - 1]! + PLAN[i - 1]!.duration - FADE)], []);
export const SCENES = PLAN.map((s, i) => ({
  ...s,
  duration: i < PLAN.length - 1 ? cuts[i + 1]! - cuts[i]! + FADE : s.duration,
}));

export const PROMO_DURATION = cuts[cuts.length - 1]! + PLAN[PLAN.length - 1].duration;

export const Promo: React.FC = () => (
  <AbsoluteFill>
    <TransitionSeries>
      {SCENES.map(({ id, component: Scene, duration }, i) => (
        <Fragment key={id}>
          {i > 0 && <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: FADE })} />}
          <TransitionSeries.Sequence name={id} durationInFrames={duration}>
            <Scene />
          </TransitionSeries.Sequence>
        </Fragment>
      ))}
    </TransitionSeries>
    <Audio
      src={staticFile("music.mp3")}
      volume={(f) =>
        interpolate(f, [0, 20, PROMO_DURATION - 75, PROMO_DURATION - 5], [0, 0.55, 0.55, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      }
    />
  </AbsoluteFill>
);
