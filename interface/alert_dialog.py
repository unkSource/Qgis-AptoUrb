from PyQt5.QtWidgets import QMessageBox

class AlertDialog:
    def __init__(self, window_main):
        self.main = window_main

    def warning(self, text):
        """Dispara um alerta amarelo de aviso"""
        msg = QMessageBox(self.main)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Aviso")
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def error(self, text):
        """Dispara um alerta vermelho de erro crítico"""
        msg = QMessageBox(self.main)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Erro")
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def success(self, text):
        """Dispara um alerta verde de sucesso"""
        msg = QMessageBox(self.main)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Sucesso")
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
