import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Fragment } from "react";
import { Answer, Alert, Home, Speed, Voice } from "./scenes/Product";
import { Connect, Follow } from "./scenes/Connect";
import { Data, Different, End } from "./scenes/Closing";
import { Hook, Problem, Reveal } from "./scenes/Intro";

export const FPS = 30;
export const FADE = 12;

/** The film, in order. Each scene is also its own composition in the Studio. */
export const SCENES = [
  { id: "Hook", component: Hook, duration: 150 },
  { id: "Problem", component: Problem, duration: 110 },
  { id: "Reveal", component: Reveal, duration: 110 },
  { id: "Connect", component: Connect, duration: 420 },
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

export const PROMO_DURATION = SCENES.reduce((sum, s) => sum + s.duration, 0) - FADE * (SCENES.length - 1);

export const Promo: React.FC = () => (
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
);
