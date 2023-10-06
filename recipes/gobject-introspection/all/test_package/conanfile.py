from conan import ConanFile
from conan.tools.build import can_run,cross_building
from conan.tools.cmake import CMake, cmake_layout,CMakeToolchain,CMakeDeps
from conan.tools.gnu import PkgConfig,PkgConfigDeps
from conan.tools.env import VirtualBuildEnv, VirtualRunEnv
import os


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    test_type = "explicit"

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        self.requires(self.tested_reference_str)

    def build_requirements(self):
        if self.settings.os != "Windows" and not self.conf.get("tools.gnu:pkg_config", default=False, check_type=str):
            self.tool_requires("pkgconf/2.0.3")

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()
        virtual_run_env = VirtualRunEnv(self)
        virtual_run_env.generate()   

        if self.settings.os == "Windows":
            deps = CMakeDeps(self)
            deps.generate()
        else:
            virtual_build_env = VirtualBuildEnv(self)
            virtual_build_env.generate()
            pkg_config_deps = PkgConfigDeps(self)
            pkg_config_deps.generate()

    def build(self):
        if self.settings.os != 'Windows':
            pkg_config = PkgConfig(self, "gobject-introspection-1.0", pkg_config_path=self.generators_folder)
            for tool in ["g_ir_compiler", "g_ir_generate", "g_ir_scanner"]:
                self.run('%s --version' % pkg_config.variables[tool], env="conanrun")
            self.run('g-ir-annotation-tool --version',env="conanrun")
            self.run('g-ir-inspect -h', env="conanrun")   
    
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if cross_building(self):
            bin_path = os.path.join(self.cpp.build.bindirs[0], "test_package")
            self.run(bin_path, env="conanrun")

