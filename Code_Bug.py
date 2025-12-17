import streamlit as st
import ast
import re
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze
import tempfile
import subprocess
import sys
import os
from typing import Tuple

# -----------------------------
# Helper Functions
# -----------------------------

def detect_python_issues(code: str):
    issues = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append("Bare except detected (use specific exceptions).")
            if isinstance(node, ast.Call) and hasattr(node.func, 'id'):
                if node.func.id in ['eval', 'exec']:
                    issues.append(f"Security risk: use of {node.func.id}().")
    except SyntaxError as e:
        issues.append(f"Syntax Error: {e}")
    return issues


def detect_java_issues(code: str):
    issues = []
    if re.search(r"System\.out\.println", code):
        issues.append("Debug print statements found (remove in production).")
    if re.search(r"catch\s*\(Exception", code):
        issues.append("Catching generic Exception is discouraged.")
    if re.search(r"==\s*\"", code):
        issues.append("String comparison using == detected (use .equals()).")
    return issues


def complexity_analysis(code: str, language: str):
    if language == "Python":
        blocks = cc_visit(code)
        return [(b.name, b.complexity) for b in blocks]
    return []


def quality_score(code: str):
    try:
        mi = mi_visit(code, True)
        return round(mi, 2)
    except:
        return 0.0


def refactoring_suggestions(language: str):
    if language == "Python":
        return [
            "Use list/dict comprehensions where possible",
            "Break large functions into smaller ones",
            "Use logging instead of print",
            "Follow PEP8 naming conventions"
        ]
    else:
        return [
            "Use proper exception hierarchy",
            "Avoid deeply nested loops",
            "Follow SOLID principles",
            "Remove unused imports"
        ]

# -----------------------------
# AI Explanation Helpers
# -----------------------------

def explain_issues_nl(issues, language):
    explanations = []
    for issue in issues:
        explanations.append(f"In your {language} code, the issue detected is: '{issue}'. This can lead to runtime errors, security risks, or maintenance problems. It is recommended to refactor this part following best practices.")
    return explanations


def runtime_error_detection(code, language):
    errors = []
    if language == "Python":
        try:
            compile(code, '<string>', 'exec')
        except Exception as e:
            errors.append(str(e))
    else:
        if 'public static void main' not in code:
            errors.append("Java Runtime Error Risk: main method not found.")
        if 'NullPointerException' in code:
            errors.append("Potential NullPointerException usage detected.")
    return errors


def run_python_realtime(code: str, timeout: int = 5) -> Tuple[int, str, str]:
    """Run Python code in a temporary file using the current interpreter.
    Returns (returncode, stdout, stderr). Uses a short timeout to avoid hangs.
    """
    fd, path = tempfile.mkstemp(suffix=".py")
    os.close(fd)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return -1, e.stdout or "", (str(e) or "Execution timed out")
    except Exception as e:
        return -2, "", str(e)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def explain_runtime_error(output: str, language: str):
    if not output:
        return "No runtime errors detected."
    # Provide a concise explanation based on the traceback or stderr
    lines = [l for l in output.splitlines() if l.strip()]
    if not lines:
        return "Runtime produced output but no errors present."
    # Heuristic: last non-empty line often contains exception type and message
    last = lines[-1]
    if language == "Python":
        if 'Traceback' in output:
            # find exception type line
            for l in reversed(lines):
                if ':' in l and not l.strip().startswith('File'):
                    return f"Detected runtime exception: {l.strip()} — inspect traceback above to find offending line and fix the error (e.g., NameError, TypeError, IndexError)."
        return f"Runtime stderr: {last}"
    else:
        return f"Runtime/compile message: {last}"


def run_java_realtime(code: str, timeout: int = 10) -> Tuple[int, str, str]:
    """Compile and run Java code in a temporary directory.
    Returns (returncode, stdout, stderr). If javac/java not found, return code -3.
    """
    import shutil
    javac = shutil.which('javac')
    java_exec = shutil.which('java')
    if not javac or not java_exec:
        return -3, "", "javac or java executable not found on PATH"

    # Try to detect a public class name; otherwise use Main
    m = re.search(r'public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)', code)
    class_name = m.group(1) if m else 'Main'

    tmpdir = tempfile.mkdtemp()
    try:
        filename = os.path.join(tmpdir, f"{class_name}.java")
        # If no public class detected, and code doesn't contain class, wrap into Main
        if m or re.search(r'\b(class)\b', code):
            java_source = code
        else:
            java_source = f'public class {class_name} {{\n public static void main(String[] args) {{\n{code}\n}}\n}}'

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(java_source)

        # Compile
        comp = subprocess.run([javac, filename], capture_output=True, text=True, timeout=timeout)
        if comp.returncode != 0:
            return comp.returncode, comp.stdout, comp.stderr

        # Run
        run = subprocess.run([java_exec, '-cp', tmpdir, class_name], capture_output=True, text=True, timeout=timeout)
        return run.returncode, run.stdout, run.stderr
    except subprocess.TimeoutExpired as e:
        return -1, e.stdout or "", (str(e) or "Execution timed out")
    except Exception as e:
        return -2, "", str(e)
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


def explain_java_error(stderr: str):
    if not stderr:
        return "No compilation/runtime errors detected."
    lines = [l for l in stderr.splitlines() if l.strip()]
    if not lines:
        return "Java produced output on stderr but no clear message to summarize."
    # If compilation errors, provide a short summary
    if any('error:' in l for l in lines):
        # Show first error line
        for l in lines:
            if 'error:' in l:
                return f"Compilation error detected: {l.strip()} — check the indicated file and line to fix syntax or type errors."
    # Runtime exceptions often contain Exception in thread or stack traces
    for l in reversed(lines):
        if 'Exception' in l or 'Error' in l:
            return f"Runtime exception detected: {l.strip()} — inspect stack trace above for root cause."
    return f"Java stderr: {lines[-1]}"

# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(page_title="AI Code Review Tool", layout="wide")

st.title("🤖 AI Code Review & Bug Detection Tool")
st.write("Upload your code to analyze bugs, complexity, and quality.")

language = st.selectbox("Select Programming Language", ["Python", "Java"])

uploaded_file = st.file_uploader("Upload Source Code File", type=["py", "java"])

if uploaded_file:
    code = uploaded_file.read().decode("utf-8")
    st.subheader("📄 Uploaded Code")
    st.code(code, language.lower())

    st.subheader("🐞 Bug & Security Analysis")
    if language == "Python":
        issues = detect_python_issues(code)
    else:
        issues = detect_java_issues(code)

    if issues:
        for i in issues:
            st.error(i)
    else:
        st.success("No major static-analysis issues detected")

    st.subheader("📊 Code Quality Score")
    score = quality_score(code)
    st.metric("Maintainability Index", score)

    st.subheader("🧠 Complexity Analysis")
    complexity = complexity_analysis(code, language)
    if complexity:
        for name, c in complexity:
            st.write(f"Function: {name} | Cyclomatic Complexity: {c}")
    else:
        st.info("Complexity analysis not available for this language")

    st.subheader("🔧 Refactoring Suggestions")
    for s in refactoring_suggestions(language):
        st.write("•", s)

    st.subheader("🧠 AI Natural Language Explanation")
    explanations = explain_issues_nl(issues, language)
    if explanations:
        for exp in explanations:
            st.info(exp)
    else:
        st.success("Code follows standard best practices.")

    st.subheader("💥 Runtime / Compilation Error Detection")
    runtime_errors = runtime_error_detection(code, language)
    if runtime_errors:
        for err in runtime_errors:
            st.error(err)
    else:
        st.success("No immediate runtime or compilation errors detected.")

    st.subheader("⚡ Realtime Execution")
    if language == "Python":
        if st.button("Run Uploaded Python Code"):
            with st.spinner('Executing code...'):
                rc, out, err = run_python_realtime(code, timeout=6)
            if rc == 0 and not err:
                st.success("No errors occurred during execution.")
                if out:
                    st.subheader("Program Output")
                    st.code(out)
            else:
                st.error("Errors occurred during execution.")
                if err:
                    st.subheader("Error Traceback / Stderr")
                    st.code(err)
                    st.subheader("Explanation")
                    st.info(explain_runtime_error(err, language))
                else:
                    st.info("Process exited with code: %s" % rc)
    else:
        st.subheader("⚡ Realtime Execution for Java")
        if st.button("Run Uploaded Java Code"):
            with st.spinner('Compiling and running Java code...'):
                rc, out, err = run_java_realtime(code, timeout=10)
            if rc == 0 and not err:
                st.success("No errors occurred during execution.")
                if out:
                    st.subheader("Program Output")
                    st.code(out)
            elif rc == -3:
                st.error("Java toolchain not found: javac/java must be on PATH to run Java code.")
            else:
                st.error("Errors occurred during compilation or execution.")
                if err:
                    st.subheader("Compiler / Runtime Stderr")
                    st.code(err)
                    st.subheader("Explanation")
                    st.info(explain_java_error(err))
                else:
                    st.info("Process exited with code: %s" % rc)

    st.subheader("🧠 AI Reasoning (LLM-based)")
    st.info("Integrate OpenAI / LLM API here to generate deep code review insights.")

else:
    st.warning("Please upload a code file to begin analysis.")
