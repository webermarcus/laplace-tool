"""
Laplace Transform API.

Uses SymPy as the source of truth for the math, and Claude to narrate the
step-by-step derivation. The LLM never computes the answer — it only explains
how to get from the input to the answer SymPy already produced.
"""

import os

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sympy import inverse_laplace_transform, laplace_transform, latex, symbols
from sympy import integrate, oo, exp as sym_exp, simplify, Heaviside, DiracDelta, Integral
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

load_dotenv()

app = FastAPI(title="Laplace Transform API")

# Open CORS for now — tighten to the deployed frontend origin before you ship.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://laplace-tool-2u039kuyx-webermarcus-projects.vercel.app", "https://laplacecalculate.com", "https://www.laplacecalculate.com"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Let users type `t^2` instead of `t**2`, and `2t` instead of `2*t`.
PARSE_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

t = symbols("t", positive=True)
s = symbols("s")
# Ensures parse_expr uses these exact symbols rather than creating new ones —
# if parse_expr creates its own `t`, laplace_transform sees a mismatch and
# silently returns nonsense (e.g. sin(t)/s instead of 1/(s^2+1)).
PARSE_LOCALS = {"t": t, "s": s}


class TransformRequest(BaseModel):
    expression: str
    direction: str  # "forward" or "inverse"


class TransformResponse(BaseModel):
    input_latex: str
    result_latex: str
    explanation: str


@app.get("/api/health")
def health():
    return {"status": "ok"}

def compute_forward(expr, t, s):
    """Try laplace_transform, then direct integration, then Meijer G."""
    # Attempt 1: built-in laplace_transform
    try:
        result = laplace_transform(expr, t, s, noconds=True)
        if not result.has(laplace_transform):
            return simplify(result)
    except Exception:
        pass

    # Attempt 2: direct integration (standard path)
    try:
        result = integrate(expr * sym_exp(-s * t), (t, 0, oo))
        if not isinstance(result, Integral) and not result.has(Integral):
            return simplify(result)
    except Exception:
        pass

    # Attempt 3: Meijer G integration — handles products of special functions
    try:
        result = integrate(expr * sym_exp(-s * t), (t, 0, oo), meijerg=True)
        if not isinstance(result, Integral) and not result.has(Integral):
            return simplify(result)
    except Exception:
        pass

    raise ValueError("SymPy couldn't compute this transform with any method")


def compute_inverse(expr, s, t):
    """inverse_laplace_transform is more reliable; no fallback needed usually."""
    result = inverse_laplace_transform(expr, s, t, noconds=True)
    return simplify(result)

@app.post("/api/transform", response_model=TransformResponse)
def transform(req: TransformRequest):
    # Parse
    try:
        expr = parse_expr(
            req.expression,
            transformations=PARSE_TRANSFORMS,
            local_dict=PARSE_LOCALS,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Couldn't parse expression: {e}")

    # Compute via SymPy
    try:
        if req.direction == "forward":
            result = compute_forward(expr, t, s)
            transform_desc = "Laplace transform"
            input_var, output_var = "t", "s"
        elif req.direction == "inverse":
            result = compute_inverse(expr, s, t)
            transform_desc = "inverse Laplace transform"
            input_var, output_var = "s", "t"
        else:
            raise HTTPException(status_code=400, detail="direction must be 'forward' or 'inverse'")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Computation failed: {e}")

    # Ask Claude to narrate — grounded on SymPy's answer.
    prompt = f"""You are explaining a {transform_desc} to a student.

Input function: {expr}
Input in LaTeX: {latex(expr)}
The variable is {input_var}, and the result is in terms of {output_var}.

The correct final answer, computed by SymPy, is: {result}
Answer in LaTeX: {latex(result)}

Write a clear, step-by-step derivation from input to answer.

Rules:
- Your final answer MUST equal the SymPy result above. Do not reach a different conclusion.
- Use standard transform tables and properties (linearity, frequency shift, time shift, derivative rules, partial fractions, etc.) where appropriate.
- Format all math with LaTeX: $...$ for inline, $$...$$ for display equations.
- Keep it to 3-6 steps. Explain each step briefly.
- If the result involves Heaviside (unit step) or DiracDelta, briefly explain what that means.
- Do NOT introduce your own final form; match the given answer exactly.
- Do NOT use any markdown. Output as plain text.
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = message.content[0].text
    except Exception as e:
        explanation = (
            f"*(Could not generate step-by-step explanation: {e})*\n\n"
            "The result above was computed directly by SymPy and is correct."
        )

    return TransformResponse(
        input_latex=latex(expr),
        result_latex=latex(result),
        explanation=explanation,
    )
