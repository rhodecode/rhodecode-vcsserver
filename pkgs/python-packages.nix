{
  Beaker = super.buildPythonPackage {
    name = "Beaker-1.7.0";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/97/8e/409d2e7c009b8aa803dc9e6f239f1db7c3cdf578249087a404e7c27a505d/Beaker-1.7.0.tar.gz";
      md5 = "386be3f7fe427358881eee4622b428b3";
    };
  };
  Jinja2 = super.buildPythonPackage {
    name = "Jinja2-2.8";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [MarkupSafe];
    src = fetchurl {
      url = "https://pypi.python.org/packages/f2/2f/0b98b06a345a761bec91a079ccae392d282690c2d8272e708f4d10829e22/Jinja2-2.8.tar.gz";
      md5 = "edb51693fe22c53cee5403775c71a99e";
    };
  };
  Mako = super.buildPythonPackage {
    name = "Mako-1.0.4";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [MarkupSafe];
    src = fetchurl {
      url = "https://pypi.python.org/packages/7a/ae/925434246ee90b42e8ef57d3b30a0ab7caf9a2de3e449b876c56dcb48155/Mako-1.0.4.tar.gz";
      md5 = "c5fc31a323dd4990683d2f2da02d4e20";
    };
  };
  MarkupSafe = super.buildPythonPackage {
    name = "MarkupSafe-0.23";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/c0/41/bae1254e0396c0cc8cf1751cb7d9afc90a602353695af5952530482c963f/MarkupSafe-0.23.tar.gz";
      md5 = "f5ab3deee4c37cd6a922fb81e730da6e";
    };
  };
  PasteDeploy = super.buildPythonPackage {
    name = "PasteDeploy-1.5.2";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/0f/90/8e20cdae206c543ea10793cbf4136eb9a8b3f417e04e40a29d72d9922cbd/PasteDeploy-1.5.2.tar.gz";
      md5 = "352b7205c78c8de4987578d19431af3b";
    };
  };
  Pyro4 = super.buildPythonPackage {
    name = "Pyro4-4.41";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [serpent];
    src = fetchurl {
      url = "https://pypi.python.org/packages/56/2b/89b566b4bf3e7f8ba790db2d1223852f8cb454c52cab7693dd41f608ca2a/Pyro4-4.41.tar.gz";
      md5 = "ed69e9bfafa9c06c049a87cb0c4c2b6c";
    };
  };
  WebOb = super.buildPythonPackage {
    name = "WebOb-1.3.1";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/16/78/adfc0380b8a0d75b2d543fa7085ba98a573b1ae486d9def88d172b81b9fa/WebOb-1.3.1.tar.gz";
      md5 = "20918251c5726956ba8fef22d1556177";
    };
  };
  WebTest = super.buildPythonPackage {
    name = "WebTest-1.4.3";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [WebOb];
    src = fetchurl {
      url = "https://pypi.python.org/packages/51/3d/84fd0f628df10b30c7db87895f56d0158e5411206b721ca903cb51bfd948/WebTest-1.4.3.zip";
      md5 = "631ce728bed92c681a4020a36adbc353";
    };
  };
  configobj = super.buildPythonPackage {
    name = "configobj-5.0.6";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [six];
    src = fetchurl {
      url = "https://pypi.python.org/packages/64/61/079eb60459c44929e684fa7d9e2fdca403f67d64dd9dbac27296be2e0fab/configobj-5.0.6.tar.gz";
      md5 = "e472a3a1c2a67bb0ec9b5d54c13a47d6";
    };
  };
  dulwich = super.buildPythonPackage {
    name = "dulwich-0.12.0";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/6f/04/fbe561b6d45c0ec758330d5b7f5ba4b6cb4f1ca1ab49859d2fc16320da75/dulwich-0.12.0.tar.gz";
      md5 = "f3a8a12bd9f9dd8c233e18f3d49436fa";
    };
  };
  greenlet = super.buildPythonPackage {
    name = "greenlet-0.4.7";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/7a/9f/a1a0d9bdf3203ae1502c5a8434fe89d323599d78a106985bc327351a69d4/greenlet-0.4.7.zip";
      md5 = "c2333a8ff30fa75c5d5ec0e67b461086";
    };
  };
  gunicorn = super.buildPythonPackage {
    name = "gunicorn-19.6.0";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/84/ce/7ea5396efad1cef682bbc4068e72a0276341d9d9d0f501da609fab9fcb80/gunicorn-19.6.0.tar.gz";
      md5 = "338e5e8a83ea0f0625f768dba4597530";
    };
  };
  hgsubversion = super.buildPythonPackage {
    name = "hgsubversion-1.8.6";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [mercurial subvertpy];
    src = fetchurl {
      url = "https://pypi.python.org/packages/ce/97/032e5093ad250e9908cea04395cbddb6902d587f712a79b53b2d778bdfdd/hgsubversion-1.8.6.tar.gz";
      md5 = "9310cb266031cf8d0779885782a84a5b";
    };
  };
  infrae.cache = super.buildPythonPackage {
    name = "infrae.cache-1.0.1";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [Beaker repoze.lru];
    src = fetchurl {
      url = "https://pypi.python.org/packages/bb/f0/e7d5e984cf6592fd2807dc7bc44a93f9d18e04e6a61f87fdfb2622422d74/infrae.cache-1.0.1.tar.gz";
      md5 = "b09076a766747e6ed2a755cc62088e32";
    };
  };
  mercurial = super.buildPythonPackage {
    name = "mercurial-3.8.3";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/56/bc/af1561195d43638d44bc3ac286c21f187430966234bee1f235711d80dfb6/mercurial-3.8.3.tar.gz";
      md5 = "97aced7018614eeccc9621a3dea35fda";
    };
  };
  mock = super.buildPythonPackage {
    name = "mock-1.0.1";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/15/45/30273ee91feb60dabb8fbb2da7868520525f02cf910279b3047182feed80/mock-1.0.1.zip";
      md5 = "869f08d003c289a97c1a6610faf5e913";
    };
  };
  msgpack-python = super.buildPythonPackage {
    name = "msgpack-python-0.4.6";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/15/ce/ff2840885789ef8035f66cd506ea05bdb228340307d5e71a7b1e3f82224c/msgpack-python-0.4.6.tar.gz";
      md5 = "8b317669314cf1bc881716cccdaccb30";
    };
  };
  py = super.buildPythonPackage {
    name = "py-1.4.29";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/2a/bc/a1a4a332ac10069b8e5e25136a35e08a03f01fd6ab03d819889d79a1fd65/py-1.4.29.tar.gz";
      md5 = "c28e0accba523a29b35a48bb703fb96c";
    };
  };
  pyramid = super.buildPythonPackage {
    name = "pyramid-1.6.1";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [setuptools WebOb repoze.lru zope.interface zope.deprecation venusian translationstring PasteDeploy];
    src = fetchurl {
      url = "https://pypi.python.org/packages/30/b3/fcc4a2a4800cbf21989e00454b5828cf1f7fe35c63e0810b350e56d4c475/pyramid-1.6.1.tar.gz";
      md5 = "b18688ff3cc33efdbb098a35b45dd122";
    };
  };
  pyramid-jinja2 = super.buildPythonPackage {
    name = "pyramid-jinja2-2.5";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [pyramid zope.deprecation Jinja2 MarkupSafe];
    src = fetchurl {
      url = "https://pypi.python.org/packages/a1/80/595e26ffab7deba7208676b6936b7e5a721875710f982e59899013cae1ed/pyramid_jinja2-2.5.tar.gz";
      md5 = "07cb6547204ac5e6f0b22a954ccee928";
    };
  };
  pyramid-mako = super.buildPythonPackage {
    name = "pyramid-mako-1.0.2";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [pyramid Mako];
    src = fetchurl {
      url = "https://pypi.python.org/packages/f1/92/7e69bcf09676d286a71cb3bbb887b16595b96f9ba7adbdc239ffdd4b1eb9/pyramid_mako-1.0.2.tar.gz";
      md5 = "ee25343a97eb76bd90abdc2a774eb48a";
    };
  };
  pytest = super.buildPythonPackage {
    name = "pytest-2.8.5";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [py];
    src = fetchurl {
      url = "https://pypi.python.org/packages/b1/3d/d7ea9b0c51e0cacded856e49859f0a13452747491e842c236bbab3714afe/pytest-2.8.5.zip";
      md5 = "8493b06f700862f1294298d6c1b715a9";
    };
  };
  repoze.lru = super.buildPythonPackage {
    name = "repoze.lru-0.6";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/6e/1e/aa15cc90217e086dc8769872c8778b409812ff036bf021b15795638939e4/repoze.lru-0.6.tar.gz";
      md5 = "2c3b64b17a8e18b405f55d46173e14dd";
    };
  };
  rhodecode-vcsserver = super.buildPythonPackage {
    name = "rhodecode-vcsserver-4.1.2";
    buildInputs = with self; [mock pytest WebTest];
    doCheck = true;
    propagatedBuildInputs = with self; [configobj dulwich hgsubversion infrae.cache mercurial msgpack-python pyramid Pyro4 simplejson subprocess32 waitress WebOb];
    src = ./.;
  };
  serpent = super.buildPythonPackage {
    name = "serpent-1.12";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/3b/19/1e0e83b47c09edaef8398655088036e7e67386b5c48770218ebb339fbbd5/serpent-1.12.tar.gz";
      md5 = "05869ac7b062828b34f8f927f0457b65";
    };
  };
  setuptools = super.buildPythonPackage {
    name = "setuptools-20.8.1";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/c4/19/c1bdc88b53da654df43770f941079dbab4e4788c2dcb5658fb86259894c7/setuptools-20.8.1.zip";
      md5 = "fe58a5cac0df20bb83942b252a4b0543";
    };
  };
  simplejson = super.buildPythonPackage {
    name = "simplejson-3.7.2";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/6d/89/7f13f099344eea9d6722779a1f165087cb559598107844b1ac5dbd831fb1/simplejson-3.7.2.tar.gz";
      md5 = "a5fc7d05d4cb38492285553def5d4b46";
    };
  };
  six = super.buildPythonPackage {
    name = "six-1.9.0";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/16/64/1dc5e5976b17466fd7d712e59cbe9fb1e18bec153109e5ba3ed6c9102f1a/six-1.9.0.tar.gz";
      md5 = "476881ef4012262dfc8adc645ee786c4";
    };
  };
  subprocess32 = super.buildPythonPackage {
    name = "subprocess32-3.2.6";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/28/8d/33ccbff51053f59ae6c357310cac0e79246bbed1d345ecc6188b176d72c3/subprocess32-3.2.6.tar.gz";
      md5 = "754c5ab9f533e764f931136974b618f1";
    };
  };
  subvertpy = super.buildPythonPackage {
    name = "subvertpy-0.9.3";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://github.com/jelmer/subvertpy/archive/subvertpy-0.9.3.tar.gz";
      md5 = "7b745a47128050ea5a73efcd913ec1cf";
    };
  };
  translationstring = super.buildPythonPackage {
    name = "translationstring-1.3";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/5e/eb/bee578cc150b44c653b63f5ebe258b5d0d812ddac12497e5f80fcad5d0b4/translationstring-1.3.tar.gz";
      md5 = "a4b62e0f3c189c783a1685b3027f7c90";
    };
  };
  venusian = super.buildPythonPackage {
    name = "venusian-1.0";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/86/20/1948e0dfc4930ddde3da8c33612f6a5717c0b4bc28f591a5c5cf014dd390/venusian-1.0.tar.gz";
      md5 = "dccf2eafb7113759d60c86faf5538756";
    };
  };
  waitress = super.buildPythonPackage {
    name = "waitress-0.8.9";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [setuptools];
    src = fetchurl {
      url = "https://pypi.python.org/packages/ee/65/fc9dee74a909a1187ca51e4f15ad9c4d35476e4ab5813f73421505c48053/waitress-0.8.9.tar.gz";
      md5 = "da3f2e62b3676be5dd630703a68e2a04";
    };
  };
  wheel = super.buildPythonPackage {
    name = "wheel-0.29.0";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [];
    src = fetchurl {
      url = "https://pypi.python.org/packages/c9/1d/bd19e691fd4cfe908c76c429fe6e4436c9e83583c4414b54f6c85471954a/wheel-0.29.0.tar.gz";
      md5 = "555a67e4507cedee23a0deb9651e452f";
    };
  };
  zope.deprecation = super.buildPythonPackage {
    name = "zope.deprecation-4.1.1";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [setuptools];
    src = fetchurl {
      url = "https://pypi.python.org/packages/c5/c9/e760f131fcde817da6c186a3f4952b8f206b7eeb269bb6f0836c715c5f20/zope.deprecation-4.1.1.tar.gz";
      md5 = "ce261b9384066f7e13b63525778430cb";
    };
  };
  zope.interface = super.buildPythonPackage {
    name = "zope.interface-4.1.3";
    buildInputs = with self; [];
    doCheck = false;
    propagatedBuildInputs = with self; [setuptools];
    src = fetchurl {
      url = "https://pypi.python.org/packages/9d/81/2509ca3c6f59080123c1a8a97125eb48414022618cec0e64eb1313727bfe/zope.interface-4.1.3.tar.gz";
      md5 = "9ae3d24c0c7415deb249dd1a132f0f79";
    };
  };

### Test requirements

  
}
