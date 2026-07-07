import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; error?: Error; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };
  static getDerivedStateFromError(error: Error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div style={{padding:20,color:"#ff3355",fontFamily:"monospace",fontSize:13}}>
          Errore: {this.state.error?.message}
        </div>
      );
    }
    return this.props.children;
  }
}
