"""Re-export pure range parser from domain."""

from jplearn_api.domain.range_parser import RangeNotSatisfiable, parse_byte_range

__all__ = ["RangeNotSatisfiable", "parse_byte_range"]
