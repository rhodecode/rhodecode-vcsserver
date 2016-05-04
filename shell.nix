{ pkgs ? (import <nixpkgs> {})
}:

let
  vcsserver = import ./default.nix {inherit pkgs;};

in vcsserver.override (attrs: {

  # Avoid that we dump any sources into the store when entering the shell and
  # make development a little bit more convenient.
  src = null;

})
