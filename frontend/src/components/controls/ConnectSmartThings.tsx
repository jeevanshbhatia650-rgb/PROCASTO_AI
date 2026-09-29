import { useStore } from "../../lib/store";

/** F23: shown only when the backend runs against real SmartThings devices and isn't linked yet. */
export function ConnectSmartThings() {
  const hello = useStore((s) => s.hello);
  if (hello?.provider !== "smartthings" || hello.smartthings_connected) return null;
  return (
    <a
      href="/auth/smartthings/login"
      className="pressable rounded-full bg-primary-on-dark/15 px-3 py-1 text-primary-on-dark transition-colors duration-150 hover:bg-primary-on-dark/25"
    >
      Connect SmartThings
    </a>
  );
}
