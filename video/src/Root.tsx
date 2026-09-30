import "./index.css";
import { Composition, Folder } from "remotion";
import { FPS, Promo, PROMO_DURATION, SCENES } from "./Promo";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Promo" component={Promo} width={1920} height={1080} fps={FPS} durationInFrames={PROMO_DURATION} />
    <Folder name="Scenes">
      {SCENES.map(({ id, component, duration }) => (
        <Composition key={id} id={id} component={component} width={1920} height={1080} fps={FPS} durationInFrames={duration} />
      ))}
    </Folder>
  </>
);
