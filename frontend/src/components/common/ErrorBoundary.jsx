import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[50vh] flex items-center justify-center p-4">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 bg-error/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-error" />
            </div>
            <h2 className="font-heading text-xl font-bold text-gray-900 mb-2">Something went wrong</h2>
            <p className="text-gray-500 text-sm mb-6">
              An unexpected error occurred. Please try again or go back to the home page.
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="flex items-center gap-2 bg-primary hover:bg-primary-dark text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
              >
                <RefreshCw className="w-4 h-4" /> Try Again
              </button>
              <a
                href="/"
                className="flex items-center gap-2 border border-gray-300 hover:border-gray-400 font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
              >
                Go Home
              </a>
            </div>
            {import.meta.env.DEV && this.state.error && (
              <details className="mt-6 text-left bg-gray-50 rounded-lg p-4">
                <summary className="text-xs font-medium text-gray-500 cursor-pointer">Error details</summary>
                <pre className="mt-2 text-xs text-error overflow-auto max-h-40">
                  {this.state.error.toString()}
                </pre>
              </details>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
