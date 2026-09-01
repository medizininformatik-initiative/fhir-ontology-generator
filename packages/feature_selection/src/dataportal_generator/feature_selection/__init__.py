from dataportal_generator.common.config.project import register_config_module

from dataportal_generator.feature_selection.config import FeatureSelectionConfig

# Config module registration
register_config_module("feature_selection", FeatureSelectionConfig)