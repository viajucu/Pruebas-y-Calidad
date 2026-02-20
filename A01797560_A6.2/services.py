"""
services.py

Implementar la capa de reglas de negocio del sistema de reservaciones,
orquestando los repositorios de persistencia (archivos JSON) y los
modelos de dominio (Hotel, Customer, Reservation).

Objetivos principales (alineados con los requisitos del ejercicio):
    - Métodos con persistencia para Hotels, Customer y Reservation
    - Centralizar reglas de negocio:
    - Comunicación clara de errores mediante excepciones semánticas
    - Mantener separación de responsabilidades

"""
