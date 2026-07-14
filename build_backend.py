import os
import sys
import shutil
import subprocess
from setuptools import build_meta as _orig

def build_cpp():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ext_dir = os.path.join(base_dir, "external", "gridappsd-state-estimator")
    
    # 1. Ensure SuiteSparse and json submodules are cloned
    ss_dir = os.path.join(ext_dir, "SuiteSparse")
    if not os.path.exists(ss_dir):
        print("Cloning SuiteSparse dependency...", flush=True)
        subprocess.run(["git", "clone", "https://github.com/GRIDAPPSD/SuiteSparse"], cwd=ext_dir, check=True)
        
    json_dir = os.path.join(ext_dir, "json")
    if not os.path.exists(json_dir):
        print("Cloning json dependency...", flush=True)
        subprocess.run(["git", "clone", "https://github.com/GRIDAPPSD/json"], cwd=ext_dir, check=True)
        
    # 2. Find helics installation path dynamically from python helics package
    import helics
    helics_install_path = os.path.join(os.path.dirname(helics.__file__), "install")
    print(f"Using HELICS installation path: {helics_install_path}", flush=True)

    # 3. Build only the required SuiteSparse libraries (avoiding LAPACK, BLAS, and CMake dependencies)
    # The state estimator only links against: -lklu -lamd -lbtf -lcolamd -lcxsparse -lsuitesparseconfig
    ss_components = [
        "SuiteSparse_config",
        "AMD",
        "BTF",
        "COLAMD",
        "CXSparse",
        "KLU"
    ]
    
    ss_dir_abs = os.path.abspath(ss_dir)
    ss_lib_dir = os.path.join(ss_dir_abs, "lib")
    
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = ss_lib_dir + (":" + env.get("LD_LIBRARY_PATH", "") if env.get("LD_LIBRARY_PATH") else "")
    
    for comp in ss_components:
        comp_dir = os.path.join(ss_dir, comp)
        print(f"Compiling SuiteSparse component {comp}...", flush=True)
        subprocess.run(
            ["make", "library", f"INSTALL={ss_dir_abs}"],
            cwd=comp_dir,
            env=env,
            check=True
        )
        print(f"Installing SuiteSparse component {comp}...", flush=True)
        subprocess.run(
            ["make", "install", f"INSTALL={ss_dir_abs}"],
            cwd=comp_dir,
            env=env,
            check=True
        )
    
    # 4. Build state-estimator with overridden HELICS path and 'gadal' target
    print("Compiling state-estimator binary...", flush=True)
    ss_lib_paths = "-L../SuiteSparse/SuiteSparse_config -L../SuiteSparse/CXSparse/Lib -L../SuiteSparse/AMD/Lib -L../SuiteSparse/BTF/Lib -L../SuiteSparse/COLAMD/Lib -L../SuiteSparse/KLU/Lib"
    ss_libs = "-lklu -lamd -lbtf -lcolamd -lcxsparse -lsuitesparseconfig -lstdc++"
    gadal_libs = f"{ss_lib_paths} {ss_libs} -L{helics_install_path}/lib -L{helics_install_path}/lib64 -Wl,-rpath,{helics_install_path}/lib -Wl,-rpath,{helics_install_path}/lib64 -lhelics"
    
    extra_cxxflags = os.environ.get("STATE_ESTIMATOR_DEFINES", "")
    subprocess.run(
        [
            "make",
            "-C",
            "state-estimator",
            "gadal",
            f"HELICS={helics_install_path}",
            f"GADAL_LIBS={gadal_libs}",
            f"EXTRA_CXXFLAGS={extra_cxxflags}"
        ],
        cwd=ext_dir,
        env=env,
        check=True
    )
    
    # 5. Copy compiled binary to target directories
    bin_src = os.path.join(ext_dir, "state-estimator", "bin", "state-estimator-gadal")
    if not os.path.exists(bin_src):
        raise FileNotFoundError(f"Expected compiled binary not found at {bin_src}")
        
    dest_dir = os.path.join(base_dir, "src", "ekf_federate", "bin")
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(bin_src, os.path.join(dest_dir, "state-estimator-gadal"))
    
    root_bin_dir = os.path.join(base_dir, "bin")
    os.makedirs(root_bin_dir, exist_ok=True)
    shutil.copy2(bin_src, os.path.join(root_bin_dir, "state-estimator-gadal"))
    
    print("Successfully built and copied state-estimator-gadal binary.", flush=True)

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    build_cpp()
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)

def build_sdist(sdist_directory, config_settings=None):
    build_cpp()
    return _orig.build_sdist(sdist_directory, config_settings)

def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    build_cpp()
    if hasattr(_orig, 'build_editable'):
        return _orig.build_editable(wheel_directory, config_settings, metadata_directory)
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)

get_requires_for_build_wheel = _orig.get_requires_for_build_wheel
get_requires_for_build_sdist = _orig.get_requires_for_build_sdist
prepare_metadata_for_build_wheel = _orig.prepare_metadata_for_build_wheel
if hasattr(_orig, 'get_requires_for_build_editable'):
    get_requires_for_build_editable = _orig.get_requires_for_build_editable
if hasattr(_orig, 'prepare_metadata_for_build_editable'):
    prepare_metadata_for_build_editable = _orig.prepare_metadata_for_build_editable
