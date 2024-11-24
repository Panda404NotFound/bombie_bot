from dataclasses import dataclass, field
from typing import Dict, Set, List

@dataclass
class BoxCoordinates:
    """Координаты четырехточечной области взаимодействия"""
    # Верхние точки
    top_left_x: float
    top_left_y: float
    top_right_x: float
    top_right_y: float
    # Нижние точки
    bottom_left_x: float
    bottom_left_y: float
    bottom_right_x: float
    bottom_right_y: float
    
    def contains_point(self, x: float, y: float) -> bool:
        """Проверка принадлежности точки области"""
        # Проверяем, находится ли точка внутри четырехугольника
        def area(x1, y1, x2, y2, x3, y3):
            return abs((x1*(y2-y3) + x2*(y3-y1)+ x3*(y1-y2))/2.0)
            
        # Площадь всего четырехугольника
        A = area(self.top_left_x, self.top_left_y,
                self.top_right_x, self.top_right_y,
                self.bottom_right_x, self.bottom_right_y) + \
            area(self.top_left_x, self.top_left_y,
                self.bottom_left_x, self.bottom_left_y,
                self.bottom_right_x, self.bottom_right_y)
                
        # Площади треугольников с проверяемой точкой
        A1 = area(x, y, self.top_left_x, self.top_left_y,
                 self.top_right_x, self.top_right_y)
        A2 = area(x, y, self.top_right_x, self.top_right_y,
                 self.bottom_right_x, self.bottom_right_y)
        A3 = area(x, y, self.bottom_right_x, self.bottom_right_y,
                 self.bottom_left_x, self.bottom_left_y)
        A4 = area(x, y, self.bottom_left_x, self.bottom_left_y,
                 self.top_left_x, self.top_left_y)
                 
        return abs(A - (A1 + A2 + A3 + A4)) < 1e-10

@dataclass
class BoxObject:
    """Хранение информации о box объекте"""
    coordinates: BoxCoordinates
    valid_points: set = field(default_factory=set)
    invalid_points: set = field(default_factory=set)
    
    def add_valid_point(self, x: int, y: int):
        self.valid_points.add((x, y))
        if (x, y) in self.invalid_points:
            self.invalid_points.remove((x, y))
            
    def add_invalid_point(self, x: int, y: int):
        if (x, y) not in self.valid_points:
            self.invalid_points.add((x, y))
            
    def is_valid_point(self, x: int, y: int) -> bool:
        return (x, y) in self.valid_points

@dataclass
class GlobalBoxStorage:
    """Глобальное хранилище box объектов"""
    objects: Dict[str, BoxObject] = field(default_factory=dict)
    
    def add_object(self, name: str, coordinates: BoxCoordinates):
        self.objects[name] = BoxObject(coordinates)
        
    def update_valid_point(self, name: str, x: int, y: int):
        if name in self.objects:
            self.objects[name].add_valid_point(x, y)
            
    def update_invalid_point(self, name: str, x: int, y: int):
        if name in self.objects:
            self.objects[name].add_invalid_point(x, y)

# Глобальный объект для хранения box объектов
box_storage = GlobalBoxStorage()