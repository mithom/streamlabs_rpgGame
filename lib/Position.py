from StaticData import Map


class Position(object):
    def __init__(self, x, y):
        self._location = None
        self._x = x
        self._y = y

    @property
    def location(self):
        if self._location is None:
            self._location = Map.get_map()[self._y][self._x]
        return self._location

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def coord(self):
        return self._x, self._y

    @coord.setter
    def coord(self, tupl):
        self._x = tupl[0]
        self._y = tupl[1]
        self._location = Map.get_map()[self._y][self._x]

    def __eq__(self, other):
        return self.coord == other.coord

    def __ne__(self, other):
        return not (self == other)

    def can_move_to(self, x_change, y_change):
        return (0 <= self._x + x_change < Map.x_max) and\
               (0 <= self._y + y_change < Map.y_max) and\
            Map.get_map()[self._y + y_change][self._x + x_change] is not None

    def flee_options(self):
        options = [[self._x-1, self._y], [self._x+1, self._y], [self._x, self._y-1], [self._x, self._y+1]]
        return [pos for pos in options if self.can_move_to(*pos)]
