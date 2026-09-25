{
  description = "Glaze - Universal Filename Sanitizer, Case Transformer & Batch Rename Engine";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }: let
    systems = flake-utils.lib.defaultSystems;
  in
    flake-utils.lib.eachSystem systems (system: let
      pkgs = import nixpkgs {inherit system;};
      lib = pkgs.lib;

      glazePackage = pkgs.python3Packages.buildPythonApplication {
        pname = "glaze";
        version = "0.1.0";
        src = ./.;
        pyproject = true;

        build-system = [
          pkgs.python3Packages.setuptools
        ];

        doCheck = false;

        meta = with lib; {
          description = "Universal filename sanitizer, case transformer, and batch rename engine";
          homepage = "https://github.com/SpanishSyntax/Glaze";
          license = licenses.mit;
          mainProgram = "glaze";
        };
      };
    in {
      packages = {
        default = glazePackage;
        glaze = glazePackage;
      };

      apps = {
        default = {
          type = "app";
          program = "${glazePackage}/bin/glaze";
        };
        glaze = {
          type = "app";
          program = "${glazePackage}/bin/glaze";
        };
        capspace = {
          type = "app";
          program = "${glazePackage}/bin/capspace";
        };
      };

      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          python3
          python3Packages.setuptools
        ];
      };
    })
    // {
      homeManagerModules = {
        default = self.homeManagerModules.glaze;
        glaze = {
          config,
          lib,
          pkgs,
          ...
        }: let
          cfg = config.programs.glaze;
          system = pkgs.stdenv.hostPlatform.system;
          defaultGlaze = self.packages.${system}.default;
        in {
          options.programs.glaze = {
            enable = lib.mkEnableOption "Glaze - Universal filename sanitizer & case transformer";

            package = lib.mkOption {
              type = lib.types.package;
              default = defaultGlaze;
              description = "The Glaze package to use.";
            };
          };

          config = lib.mkIf cfg.enable {
            home.packages = [cfg.package];
          };
        };
      };
    };
}
