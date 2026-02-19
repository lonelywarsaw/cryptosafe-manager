from abc import ABC, abstractmethod

class EncryptionService(ABC):
    @abstractmethod
    def encrypt(self, data, key):
        pass

    @abstractmethod
    def decrypt(self, ciphertext, key):
        pass
