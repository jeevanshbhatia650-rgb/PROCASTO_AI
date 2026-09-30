# The PROCASTO film

The 92-second promo film, made with [Remotion](https://www.remotion.dev) (React for video). App scenes use real
screen captures from the running site (`public/shot-*.png`); the SmartThings connect and follow sequences are
animated and labelled as an illustration with sample devices. Music: "lo-fi beat" by zephiramusic.

```bash
npm install
npm run dev
```

```bash
npx remotion render Promo out/procasto-promo.mp4
```

Every scene is its own composition in the Studio (folder "Scenes"); cuts snap to the music's 76 BPM beat
(`src/Promo.tsx`). The web copy used on the site lives at `frontend/public/media/procasto-film.mp4`.
