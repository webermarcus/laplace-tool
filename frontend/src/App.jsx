import { useState } from 'react';
import { BlockMath, InlineMath } from 'react-katex';

// In prod, set VITE_API_BASE to your deployed backend URL (e.g. https://laplace-tool-api.fly.dev).
// In dev, leave it empty — vite.config.js proxies /api to localhost:8000.
const API_BASE = import.meta.env.VITE_API_BASE || '';

/**
 * Minimal inline renderer that splits a string into plain text + KaTeX blocks
 * based on $$...$$ (display) and $...$ (inline) delimiters.
 * For an MVP this is fine; swap in a real markdown-with-math renderer later.
 */
function renderWithMath(text) {
  const parts = [];
  let rest = text;
  let key = 0;

  while (rest.length > 0) {
    const displayMatch = rest.match(/\$\$([\s\S]+?)\$\$/);
    const inlineMatch = rest.match(/\$([^$\n]+?)\$/);

    let firstIdx = Infinity;
    let type = null;
    let match = null;

    if (displayMatch && displayMatch.index < firstIdx) {
      firstIdx = displayMatch.index;
      type = 'display';
      match = displayMatch;
    }
    if (inlineMatch && inlineMatch.index < firstIdx) {
      firstIdx = inlineMatch.index;
      type = 'inline';
      match = inlineMatch;
    }

    if (!match) {
      parts.push(<span key={key++}>{rest}</span>);
      break;
    }

    if (firstIdx > 0) {
      parts.push(<span key={key++}>{rest.slice(0, firstIdx)}</span>);
    }

    if (type === 'display') {
      parts.push(<BlockMath key={key++} math={match[1]} />);
    } else {
      parts.push(<InlineMath key={key++} math={match[1]} />);
    }

    rest = rest.slice(firstIdx + match[0].length);
  }

  return parts;
}

export default function App() {
  const [expression, setExpression] = useState('sin(t)');
  const [direction, setDirection] = useState('forward');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/transform`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression, direction }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const inputHint =
    direction === 'forward'
      ? 'Examples: sin(t), t^2, exp(-2*t), t*cos(3*t)'
      : 'Examples: 1/(s^2 + 1), s/(s-3), 1/(s^2 + 2*s + 5)';

  return (
    <div className="container">
      <header>
        <h1>Laplace Transform Calculator</h1>
        <p className="subtitle">
          Computes forward and inverse Laplace transforms with step-by-step explanations.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="input-form">
        <div className="direction-toggle">
          <label>
            <input
              type="radio"
              value="forward"
              checked={direction === 'forward'}
              onChange={(e) => setDirection(e.target.value)}
            />
            <span>Laplace &nbsp;(f(t) → F(s))</span>
          </label>
          <label>
            <input
              type="radio"
              value="inverse"
              checked={direction === 'inverse'}
              onChange={(e) => setDirection(e.target.value)}
            />
            <span>Inverse &nbsp;(F(s) → f(t))</span>
          </label>
        </div>

        <label className="expression-label">
          Expression
          <input
            type="text"
            value={expression}
            onChange={(e) => setExpression(e.target.value)}
            placeholder={inputHint}
            className="expression-input"
            autoFocus
          />
        </label>
        <p className="hint">{inputHint}</p>

        <button type="submit" disabled={loading || !expression.trim()}>
          {loading ? 'Computing…' : 'Transform'}
        </button>
      </form>

      {error && <div className="error">Error: {error}</div>}

      {result && (
        <div className="result">
          <section>
            <h2>Input</h2>
            <BlockMath math={result.input_latex} />
          </section>

          <section>
            <h2>Result</h2>
            <BlockMath math={result.result_latex} />
          </section>

          <section>
            <h2>Step-by-step</h2>
            <div className="explanation">{renderWithMath(result.explanation)}</div>
          </section>
        </div>
      )}

      <footer>
        <p>
          Math by SymPy. Explanations by Claude, grounded on the SymPy answer.
          Explanations may contain reasoning errors. The final result is always correct.
        </p>
      </footer>
    </div>
  );
}
