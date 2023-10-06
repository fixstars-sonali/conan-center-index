from conan import ConanFile
from conan.tools.meson import Meson, MesonToolchain
from conan.tools.env import VirtualBuildEnv, VirtualRunEnv
from conan.errors import ConanInvalidConfiguration
from conan.tools.layout import basic_layout
from conan.tools.build import cross_building
from conan.tools.apple import fix_apple_shared_install_name, is_apple_os
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
from conan.tools.files import apply_conandata_patches, chdir,  export_conandata_patches, get, rename, rm, rmdir,replace_in_file,copy
from conan.tools.gnu import PkgConfigDeps, PkgConfig
from conan.tools.scm import Version
import os
import glob

required_conan_version = ">=1.56.0 <2 || >=2.0.6"

class GobjectIntrospectionConan(ConanFile):
    name = "gobject-introspection"
    description = "GObject introspection is a middleware layer between C libraries (using GObject) and language bindings"
    topics = ("conan", "gobject-instrospection")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://gitlab.gnome.org/GNOME/gobject-introspection"
    license = "LGPL-2.1"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False], 
        "fPIC": [True, False],
        "with_cairo":[True, False],
        }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_cairo": False,
        }

    def export_sources(self):
        export_conandata_patches(self)

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        self.settings.rm_safe("compiler.cppstd")
        self.settings.rm_safe("compiler.libcxx")
        if self.options.shared:
            self.options["glib"].shared = True

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        # if self.settings.os == "Windows":
        #     raise ConanInvalidConfiguration("%s recipe does not support windows. Contributions are welcome!" % self.name)
    def layout(self):
        basic_layout(self, src_folder="src")

    def build_requirements(self):
        if Version(self.version) >= "1.71.0":
            self.tool_requires("meson/1.2.2")
        else:
            # https://gitlab.gnome.org/GNOME/gobject-introspection/-/issues/414
            self.tool_requires("meson/0.59.3")
        self.tool_requires("pkgconf/2.0.3")
        if self.settings.os == "Windows":
            self.tool_requires("winflexbison/2.5.25")
        else:
            self.tool_requires("flex/2.6.4")
            self.tool_requires("bison/3.8.2")

    def requirements(self):
        # glib-object.h and gio/gio.h are used in several public headers
        self.requires("glib/2.78.0", transitive_headers=True)
        self.requires("libffi/3.4.4", transitive_headers=True)
        if self.options.with_cairo:
            self.requires("cairo/1.17.6")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        env = VirtualBuildEnv(self)
       
        env.generate()
        if not cross_building(self):
            env = VirtualRunEnv(self)
            env.generate(scope="build")

        deps = PkgConfigDeps(self)
        deps.generate()

        tc = MesonToolchain(self)
        tc.project_options["cairo"] = "enabled" if self.options.with_cairo else "disabled"
        tc.project_options["build_introspection_data"] = self.dependencies["glib"].options.shared       
        tc.project_options["datadir"] = os.path.join(self.package_folder, "res")
        tc.generate()

   

    def validate(self):
        if is_msvc_static_runtime(self):
            raise ConanInvalidConfiguration("Static runtime is not supported on Windows due to GLib issues")
        if self.options.shared and not self.dependencies["glib"].options.shared:
            raise ConanInvalidConfiguration("Shared gobject-introspection cannot link to static GLib")
        if is_apple_os(self) and self.dependencies["glib"].options.shared:
            raise ConanInvalidConfiguration(
                "macOS builds are disabled when glib is shared until "
                "conan-io/conan#7324 gets merged to fix macOS SIP issue #8443"
            )

    def build(self):
        apply_conandata_patches(self)
        replace_in_file(
            self,
            os.path.join(self.source_folder, "meson.build"),
            "subdir('tests')",
            "#subdir('tests')",
        )
        
        if is_msvc(self):
            self.buildenv.append_path("PKG_CONFIG_PATH",self.generators_folder)
        meson = Meson(self)
        meson.configure()
        meson.build()

    def _fix_library_names(self, path):
        # https://github.com/mesonbuild/meson/issues/1412
        if not self.options.shared and is_msvc(self):
            with chdir(self, path):
                for filename_old in glob.glob("*.a"):
                    filename_new = filename_old[3:-2] + ".lib"
                    self.output.info(f"rename {filename_old} into {filename_new}")
                    rename(self, filename_old, filename_new)


    def package(self):
        copy(self, "COPYING", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        meson = Meson(self)
        meson.install()
        self._fix_library_names(os.path.join(self.package_folder, "lib"))   

        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "share"))
        rm(self, "*.pdb", self.package_folder, recursive=True)
        fix_apple_shared_install_name(self)

    def package_info(self):
        self.cpp_info.libs = ["girepository-1.0"]

        self.cpp_info.includedirs.append(
            os.path.join("include", "gobject-introspection-1.0")
        )
        self.cpp_info.libdirs = ['lib']  
        self.cpp_info.bindirs = ['bin'] 
        self.cpp_info.set_property("pkg_config_name", "gobject-introspection-1.0")

        # self.cpp_info.names["pkg_config"] = "gobject-introspection-1.0"
        bin_path = os.path.join(self.package_folder, "bin")
        self.output.info("Appending PATH environment variable: {}".format(bin_path))
        self.env_info.PATH.append(bin_path)

        exe_ext = ".exe" if self.settings.os == "Windows" else ""

        pkgconfig_variables = {
            'datadir': '${prefix}/res',
            'bindir': '${prefix}/bin',
            'g_ir_scanner': '${bindir}/g-ir-scanner',
            'g_ir_compiler': '${bindir}/g-ir-compiler%s' % exe_ext,
            'g_ir_generate': '${bindir}/g-ir-generate%s' % exe_ext,
            'gidatadir': '${datadir}/gobject-introspection-1.0',
            'girdir': '${datadir}/gir-1.0',
            'typelibdir': '${libdir}/girepository-1.0',
        }
        self.cpp_info.set_property(
            "pkg_config_custom_content",
            "\n".join("%s=%s" % (key, value) for key,value in pkgconfig_variables.items()))
