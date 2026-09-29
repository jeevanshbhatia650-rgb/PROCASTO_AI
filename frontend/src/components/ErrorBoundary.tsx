import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { name: string; children: ReactNode };
type State = { failed: boolean };

/** One broken panel must never take the whole demo down with it. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[${this.props.name}] crashed`, error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="rounded-lg border border-bad/30 bg-bad/5 p-4 t-caption text-bad-text">
        The {this.props.name} panel hit an error.{" "}
        <button type="button" className="underline" onClick={() => this.setState({ failed: false })}>
          Try again
        </button>
      </div>
    );
  }
}
