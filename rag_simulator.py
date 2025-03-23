import sys
import networkx as nx
import math  # Added for math module
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QGraphicsScene, 
                            QGraphicsView, QDialog, QLineEdit, QRadioButton, 
                            QMessageBox, QButtonGroup, QGraphicsItem, QSpinBox)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QBrush, QColor, QPainter, QKeySequence, QShortcut

class GraphicsNode(QGraphicsItem):
    def __init__(self, x, y, name, node_type, instances=1):
        super().__init__()
        self.name = name
        self.node_type = node_type
        self.instances = instances  # Number of instances for resources
        self.available_instances = instances  # Currently available instances
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.size = 50
        self.is_in_deadlock = False

    def boundingRect(self):
        return QRectF(0, 0, self.size, self.size)

    def paint(self, painter: QPainter, option, widget):
        if self.is_in_deadlock:
            process_color = QColor(255, 100, 100)
            resource_color = QColor(255, 150, 150)
        else:
            process_color = QColor(173, 216, 230)
            resource_color = QColor(144, 238, 144)

        if self.node_type == 'process':
            painter.setBrush(QBrush(process_color))
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawEllipse(0, 0, self.size, self.size)
            painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, self.name)
        else:
            painter.setBrush(QBrush(resource_color))
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawRect(0, 0, self.size, self.size)
            # Show total and available instances
            text = f"{self.name}\n({self.available_instances}/{self.instances})"
            painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, text)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # Notify the main window that the node position has changed
            self.scene().parent().update_edges()
        return super().itemChange(change, value)

class ResourceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Resource")
        layout = QVBoxLayout(self)

        # Instance count input
        instance_layout = QHBoxLayout()
        instance_layout.addWidget(QLabel("Number of instances:"))
        self.instance_spinbox = QSpinBox()
        self.instance_spinbox.setMinimum(1)
        self.instance_spinbox.setMaximum(99)
        self.instance_spinbox.setValue(1)
        instance_layout.addWidget(self.instance_spinbox)
        layout.addLayout(instance_layout)

        # Add button
        add_button = QPushButton("Add")
        add_button.clicked.connect(self.accept)
        layout.addWidget(add_button)

class EdgeDialog(QDialog):
    def __init__(self, nodes, edge_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add {edge_type.capitalize()} Edge")
        layout = QVBoxLayout(self)

        # From node input
        from_layout = QHBoxLayout()
        from_layout.addWidget(QLabel("From:"))
        self.from_combo = QLineEdit()
        from_layout.addWidget(self.from_combo)
        layout.addLayout(from_layout)

        # To node input
        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("To:"))
        self.to_combo = QLineEdit()
        to_layout.addWidget(self.to_combo)
        layout.addLayout(to_layout)

        # Number of instances
        instances_layout = QHBoxLayout()
        instances_layout.addWidget(QLabel("Number of instances:"))
        self.instances_spinbox = QSpinBox()
        self.instances_spinbox.setMinimum(1)
        self.instances_spinbox.setMaximum(99)
        self.instances_spinbox.setValue(1)
        instances_layout.addWidget(self.instances_spinbox)
        layout.addLayout(instances_layout)

        # Add hint label based on edge type
        hint_text = ("Note: Request edges must go from Process to Resource"
                    if edge_type == 'request' else
                    "Note: Allocation edges must go from Resource to Process")
        hint_label = QLabel(hint_text)
        layout.addWidget(hint_label)

        # Add button
        add_button = QPushButton("Add")
        add_button.clicked.connect(self.accept)
        layout.addWidget(add_button)

class RAGSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Resource Allocation Graph Simulator")
        self.setGeometry(100, 100, 800, 600)

        # Initialize graph and history
        self.graph = nx.DiGraph()
        self.nodes = {}
        self.edges = []
        self.process_count = 0
        self.resource_count = 0
        self.selected_nodes = []
        
        # Add history tracking
        self.history = []  # List to store previous states
        self.save_state()  # Save initial state
        self.deadlock_edges = set()  # Add this to store deadlock edges

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create button panel
        button_panel = QHBoxLayout()
        
        # Add buttons with shortcuts
        add_process_btn = QPushButton("Add Process (P)")
        add_process_btn.clicked.connect(self.add_process)
        QShortcut(QKeySequence("P"), self, self.add_process)
        button_panel.addWidget(add_process_btn)

        add_resource_btn = QPushButton("Add Resource (R)")
        add_resource_btn.clicked.connect(self.add_resource)
        QShortcut(QKeySequence("R"), self, self.add_resource)
        button_panel.addWidget(add_resource_btn)

        request_edge_btn = QPushButton("Request Edge (Q)")
        request_edge_btn.clicked.connect(lambda: self.show_add_edge_dialog('request'))
        QShortcut(QKeySequence("Q"), self, lambda: self.show_add_edge_dialog('request'))
        button_panel.addWidget(request_edge_btn)

        allocation_edge_btn = QPushButton("Allocation Edge (A)")
        allocation_edge_btn.clicked.connect(lambda: self.show_add_edge_dialog('allocation'))
        QShortcut(QKeySequence("A"), self, lambda: self.show_add_edge_dialog('allocation'))
        button_panel.addWidget(allocation_edge_btn)

        check_deadlock_btn = QPushButton("Check Deadlock (D)")
        check_deadlock_btn.clicked.connect(self.check_deadlock)
        QShortcut(QKeySequence("D"), self, self.check_deadlock)
        button_panel.addWidget(check_deadlock_btn)

        # Add Undo button with left arrow shortcut
        undo_btn = QPushButton("Undo (←)")
        undo_btn.clicked.connect(self.undo_last_action)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.undo_last_action)
        button_panel.addWidget(undo_btn)

        layout.addLayout(button_panel)

        # Create graphics scene and view
        self.scene = QGraphicsScene()
        self.scene.setParent(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        layout.addWidget(self.view)

    def save_state(self):
        """Save current state to history"""
        state = {
            'graph': self.graph.copy(),
            'nodes': dict(self.nodes),
            'process_count': self.process_count,
            'resource_count': self.resource_count,
            'node_positions': {name: (node.pos().x(), node.pos().y(), 
                                    node.instances if node.node_type == 'resource' else 1,
                                    node.available_instances if node.node_type == 'resource' else 1) 
                             for name, node in self.nodes.items()}
        }
        self.history.append(state)

    def undo_last_action(self):
        """Revert to the previous state"""
        if len(self.history) > 1:  # Ensure we have a previous state
            self.history.pop()  # Remove current state
            previous_state = self.history[-1]  # Get previous state
            
            # Clear current scene and reset deadlock highlighting
            self.scene.clear()
            self.edges.clear()
            self.deadlock_edges.clear()
            
            # Restore previous state
            self.graph = previous_state['graph'].copy()
            self.process_count = previous_state['process_count']
            self.resource_count = previous_state['resource_count']
            
            # Recreate nodes
            self.nodes = {}
            for name, pos_data in previous_state['node_positions'].items():
                node_type = 'process' if name.startswith('P') else 'resource'
                instances = pos_data[2]
                available_instances = pos_data[3]
                node = GraphicsNode(pos_data[0], pos_data[1], name, node_type, instances)
                node.available_instances = available_instances
                node.is_in_deadlock = False  # Reset deadlock status
                self.scene.addItem(node)
                self.nodes[name] = node
            
            # Redraw edges
            self.update_edges()

    def add_process(self):
        self.process_count += 1
        name = f"P{self.process_count}"
        x = (self.process_count * 100) % 700
        y = 100
        node = GraphicsNode(x, y, name, 'process')
        self.scene.addItem(node)
        self.nodes[name] = node
        self.graph.add_node(name, node_type='process')
        self.save_state()

    def add_resource(self):
        dialog = ResourceDialog(self)
        if dialog.exec():
            self.resource_count += 1
            name = f"R{self.resource_count}"
            x = (self.resource_count * 100) % 700
            y = 300
            instances = dialog.instance_spinbox.value()
            node = GraphicsNode(x, y, name, 'resource', instances)
            self.scene.addItem(node)
            self.nodes[name] = node
            self.graph.add_node(name, node_type='resource', instances=instances)
            self.save_state()

    def show_add_edge_dialog(self, edge_type):
        dialog = EdgeDialog(list(self.nodes.keys()), edge_type, self)
        if dialog.exec():
            from_node = dialog.from_combo.text()
            to_node = dialog.to_combo.text()
            instances = dialog.instances_spinbox.value()
            
            if from_node in self.nodes and to_node in self.nodes:
                if edge_type == 'request':
                    if not (self.nodes[from_node].node_type == 'process' and 
                           self.nodes[to_node].node_type == 'resource'):
                        QMessageBox.warning(self, "Error", 
                            "Request edges must go from Process to Resource!")
                        return
                else:  # allocation
                    if not (self.nodes[from_node].node_type == 'resource' and 
                           self.nodes[to_node].node_type == 'process'):
                        QMessageBox.warning(self, "Error", 
                            "Allocation edges must go from Resource to Process!")
                        return
                    # Check available instances for allocation
                    resource_node = self.nodes[from_node]
                    if resource_node.available_instances < instances:
                        QMessageBox.warning(self, "Error", 
                            f"Only {resource_node.available_instances} instances available!")
                        return
                    resource_node.available_instances -= instances
                    resource_node.update()

                self.graph.add_edge(from_node, to_node, edge_type=edge_type, instances=instances)
                self.update_edges()
                self.save_state()
            else:
                QMessageBox.warning(self, "Error", "Invalid node names!")

    def update_edges(self):
        # Remove existing edges
        for edge in self.edges:
            self.scene.removeItem(edge)
        self.edges.clear()

        # Redraw all edges
        for edge in self.graph.edges(data=True):
            from_node = self.nodes[edge[0]]
            to_node = self.nodes[edge[1]]
            edge_type = edge[2].get('edge_type', 'request')
            instances = edge[2].get('instances', 1)

            # Calculate base positions
            start_pos = from_node.pos()
            end_pos = to_node.pos()
            base_start_x = start_pos.x() + from_node.size/2
            base_start_y = start_pos.y() + from_node.size/2
            base_end_x = end_pos.x() + to_node.size/2
            base_end_y = end_pos.y() + to_node.size/2

            # Determine if this edge is part of a deadlock
            is_deadlock_edge = (edge[0], edge[1]) in self.deadlock_edges

            # Choose color based on edge type and deadlock status
            if is_deadlock_edge:
                color = QColor(255, 0, 0)  # Bright red for deadlock edges
            else:
                color = Qt.GlobalColor.red if edge_type == 'request' else Qt.GlobalColor.green

            pen = QPen(color, 2)
            if is_deadlock_edge:
                pen.setWidth(4)

            # Calculate offset for multiple arrows
            dx = end_pos.x() - start_pos.x()
            dy = end_pos.y() - start_pos.y()
            length = math.sqrt(dx*dx + dy*dy)
            if length != 0:
                normal_x = -dy/length * 5  # Perpendicular vector for offset
                normal_y = dx/length * 5

                # Draw multiple arrows based on instances
                for i in range(instances):
                    offset = (i - (instances-1)/2)  # Center the arrows
                    start_x = base_start_x + normal_x * offset
                    start_y = base_start_y + normal_y * offset
                    end_x = base_end_x + normal_x * offset
                    end_y = base_end_y + normal_y * offset

                    # Draw main line
                    line = self.scene.addLine(start_x, start_y, end_x, end_y, pen)
                    self.edges.append(line)

                    # Add arrow head
                    arrow_size = 10
                    angle = math.atan2(end_y - start_y, end_x - start_x)
                    arrow_p1 = QPointF(end_x - arrow_size * math.cos(angle - math.pi/6),
                                     end_y - arrow_size * math.sin(angle - math.pi/6))
                    arrow_p2 = QPointF(end_x - arrow_size * math.cos(angle + math.pi/6),
                                     end_y - arrow_size * math.sin(angle + math.pi/6))
                    
                    arrow1 = self.scene.addLine(end_x, end_y, arrow_p1.x(), arrow_p1.y(), pen)
                    arrow2 = self.scene.addLine(end_x, end_y, arrow_p2.x(), arrow_p2.y(), pen)
                    self.edges.extend([arrow1, arrow2])

    def check_deadlock(self):
        # Reset previous deadlock highlighting
        self.deadlock_edges.clear()
        for node in self.nodes.values():
            node.is_in_deadlock = False
            node.update()

        # Track total requested and allocated instances for each resource
        resource_status = {}
        for node in self.nodes.values():
            if node.node_type == 'resource':
                resource_status[node.name] = {
                    'total': node.instances,
                    'allocated': 0,
                    'requested': 0,
                    'available': node.available_instances
                }

        # First pass: Count allocated instances
        for edge in self.graph.edges(data=True):
            from_node, to_node, data = edge
            edge_type = data.get('edge_type')
            instances = data.get('instances', 1)
            
            if edge_type == 'allocation':
                resource_status[from_node]['allocated'] += instances

        # Create a resource allocation graph for deadlock detection
        allocation_graph = nx.DiGraph()
        
        # Add all nodes
        for node in self.nodes.values():
            allocation_graph.add_node(node.name)

        # Add edges for deadlock detection
        for edge in self.graph.edges(data=True):
            from_node, to_node, data = edge
            edge_type = data.get('edge_type')
            instances = data.get('instances', 1)
            
            if edge_type == 'request':
                resource = to_node
                # Add request edge if requesting process is holding some resources
                # and the requested resource doesn't have enough available instances
                process = from_node
                
                # Check if process holds any resources
                holds_resources = False
                for e in self.graph.edges(data=True):
                    if (e[2].get('edge_type') == 'allocation' and 
                        e[1] == process):
                        holds_resources = True
                        break
                
                # Check if resource has enough available instances
                if (holds_resources and 
                    resource_status[resource]['available'] < instances):
                    allocation_graph.add_edge(from_node, to_node)
            else:  # allocation edge
                allocation_graph.add_edge(from_node, to_node)

        try:
            cycles = list(nx.simple_cycles(allocation_graph))
            if cycles:
                # Highlight nodes and edges involved in deadlock
                for cycle in cycles:
                    for node_name in cycle:
                        self.nodes[node_name].is_in_deadlock = True
                        self.nodes[node_name].update()

                    for i in range(len(cycle)):
                        from_node = cycle[i]
                        to_node = cycle[(i + 1) % len(cycle)]
                        self.deadlock_edges.add((from_node, to_node))

                self.update_edges()

                cycle_str = "\n".join([" → ".join(cycle) for cycle in cycles])
                QMessageBox.warning(self, "Deadlock Detection", 
                    f"Deadlock detected!\nCycles found:\n{cycle_str}")
            else:
                QMessageBox.information(self, "Deadlock Detection", 
                    "No deadlock detected.")
                
        except nx.NetworkXNoCycle:
            QMessageBox.information(self, "Deadlock Detection", 
                "No deadlock detected.")

def main():
    app = QApplication(sys.argv)
    window = RAGSimulator()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 