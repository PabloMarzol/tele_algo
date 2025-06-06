import os
import ast

def format_decorators(node):
    """Devuelve una lista de decoradores como strings, por ejemplo: @staticmethod"""
    decorators = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(f"@{dec.id}")
        elif isinstance(dec, ast.Attribute):
            decorators.append(f"@{dec.value.id}.{dec.attr}")
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(f"@{dec.func.id}(...)")
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(f"@{dec.func.value.id}.{dec.func.attr}(...)")
        else:
            decorators.append("@<desconocido>")
    return decorators

def extract_structure(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (SyntaxError, IndentationError) as e:
        return None, None, f"⚠️ Error de sintaxis: {e}"

    classes = {}
    global_functions = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = format_decorators(node)
            is_async = isinstance(node, ast.AsyncFunctionDef)
            global_functions.append({
                "name": node.name,
                "is_async": is_async,
                "decorators": decorators
            })
        elif isinstance(node, ast.ClassDef):
            methods = []
            for n in node.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decorators = format_decorators(n)
                    is_async = isinstance(n, ast.AsyncFunctionDef)
                    methods.append({
                        "name": n.name,
                        "is_async": is_async,
                        "decorators": decorators
                    })
            classes[node.name] = methods

    return classes, global_functions, None

def scan_directory(directory):
    for root, _, files in os.walk(directory):
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            continue

        print(f"\n📁 Carpeta: {root}")
        for file in py_files:
            file_path = os.path.join(root, file)
            print(f"  📄 Archivo: {file}")
            
            classes, functions, error = extract_structure(file_path)

            if error:
                print(f"    {error}")
                continue

            if classes:
                print("    🧩 Clases y métodos:")
                for cls, methods in classes.items():
                    print(f"      Clase: {cls}")
                    for method in methods:
                        prefix = "async def" if method["is_async"] else "def"
                        print(f"         └─ {prefix} {method['name']}()")
                        for deco in method["decorators"]:
                            print(f"            ↪ {deco}")

            if functions:
                print("    🔧 Funciones fuera de clases:")
                for func in functions:
                    prefix = "async def" if func["is_async"] else "def"
                    print(f"         └─ {prefix} {func['name']}()")
                    for deco in func["decorators"]:
                        print(f"            ↪ {deco}")

            if not classes and not functions:
                print("    (No se encontraron clases ni funciones)")

# USO
if __name__ == "__main__":
    path = "C:/Users/Ale/Desktop/System_root/tele_algo/SSSGGGAAA"  # <- Cambia esto por tu ruta real
    scan_directory(path)
