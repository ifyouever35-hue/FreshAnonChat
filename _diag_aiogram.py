import aiogram, sys, inspect
import aiogram.client.bot as cb
import aiogram.methods as m
print('aiogram =', aiogram.__version__)
print('bot file =', inspect.getsourcefile(cb))
print('methods file =', inspect.getsourcefile(m))
print('has GetBusinessConnection:', hasattr(m, 'GetBusinessConnection'))
print('python =', sys.executable)
