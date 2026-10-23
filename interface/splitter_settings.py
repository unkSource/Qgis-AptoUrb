from PyQt5.QtWidgets import QSplitter, QToolButton, QVBoxLayout
from PyQt5.QtCore import Qt, QByteArray


class QgsCollapsibleSplitter(QSplitter):
    """
    Um QSplitter customizado que adiciona um botão de colapso/seta 
    no topo do handle para esconder o painel da direita, igual ao QGIS.
    """

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)

        # Variáveis de estado internas
        self.mHelpCollapsed = False
        self.mSplitterState = QByteArray()

        self.setHandleWidth(14)
        # Painel da esquerda nunca colapsa totalmente
        self.setCollapsible(0, False)

        # O handle só existe após adicionarmos widgets, por isso adiamos a criação do botão
        self.button_collapse = None

    def create_collapse_button(self):
        """Monta o botão de seta no handle da direita."""
        splitter_handle = self.handle(1)
        if not splitter_handle:
            return

        handle_layout = QVBoxLayout()
        handle_layout.setContentsMargins(0, 10, 0, 0)
        handle_layout.setSpacing(0)

        self.button_collapse = QToolButton(splitter_handle)
        self.button_collapse.setAutoRaise(True)
        self.button_collapse.setFixedSize(12, 24)
        self.button_collapse.setCursor(Qt.ArrowCursor)
        self.button_collapse.setArrowType(Qt.RightArrow)

        handle_layout.addWidget(self.button_collapse)
        handle_layout.addStretch()
        splitter_handle.setLayout(handle_layout)

        # Conecta os eventos internos da própria classe
        self.button_collapse.clicked.connect(self.toggleCollapsed)
        self.splitterMoved.connect(self.splitterChanged)

    def toggleCollapsed(self):
        if self.mHelpCollapsed:
            self.restoreState(self.mSplitterState)
            self.button_collapse.setArrowType(Qt.RightArrow)
        else:
            self.mSplitterState = self.saveState()
            self.setSizes([1, 0])
            self.button_collapse.setArrowType(Qt.LeftArrow)
        self.mHelpCollapsed = not self.mHelpCollapsed

    def splitterChanged(self, pos, index):
        if not self.button_collapse:
            return
        if self.sizes()[1] == 0:
            self.mHelpCollapsed = True
            self.button_collapse.setArrowType(Qt.LeftArrow)
        else:
            self.mHelpCollapsed = False
            self.button_collapse.setArrowType(Qt.RightArrow)
