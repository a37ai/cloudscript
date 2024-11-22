from transpiler.main import convert_enhanced_hcl_to_standard
from converter.main import main_convert

if __name__ == "__main__":
    main_convert(convert_enhanced_hcl_to_standard('tests/main.cloud'))