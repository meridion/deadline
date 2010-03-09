# Deadline event driven subsystems

class DeadEvent(object):
	def __init__(self, delay):
		self.delay = delay
		self.neid = 0
		self.eid_roof = 1024

	def trigger(self):
		"""
Method called when event occurs.
		"""
		pass

	def getDelay(self):
		return self.delay

	def setEID(self, eid):
		self.eid = eid

	def getEID(self):
		return self.eid

	def elapseTime(self, time):
		"""
Elapse 'time' units of time.
If the event is triggered the function returns True
		"""
		self.delay -= time
		if self.delay <= 0.0:
			self.trigger()
			return True
		return False

class DeadEventQueue(object):
	def __init__(self):
		self.events = []
		self.eids = 0
		self.elapsing = False

	def scheduleEvent(self, event):
		"""
Schedule an event for execution.

The function shall return the event-code that can be used to cancel the event.
		"""

		eid = self.generateEID()
		event.setEID(eid)

		# Since it is possible for events to be scheduled
		# during the execution of elapseTime (which would ruin our queue)
		# (Events can re-schedule themselves upon triggering)
		# we defer those calls until the elapse call is complete
		if self.elapsing:
			self.schedules.append(event)
			return eid

		self._insertEvent(event)
		return eid

	def cancelEvent(self, eid):
		"""
Cancel an event as specified by it's EID
		"""

		# Same goes for events being cancelled
		if self.elapsing:
			self.cancels.append(eid)
		else:
			self.events = filter(lambda e: e.getEID() != eid, self.events)

	def elapseTime(self, time):
		"""
"Atomically" elapse the time of events in the queue
		"""
		self.scheds = []
		self.cancels = []

		# Do elapse
		self.elapsing = True
		self.events = filter(lambda e: not e.elapseTime(time), self.events)
		self.elapsing = False

		# Insert events scheduled in the mean time
		for e in scheds:
			self._insertEvent(e)

		for eid in cancels:
			self.cancelEvent(eid)

		del self.cancels
		del self.scheds

	def _insertEvent(self, e):
		"""
Internal function that inserts an event in the queue at the right place

e: Event to be insterted

This function returns nothing.
		"""
		d = e.getDelay()
		for i in range(len(self.events)):
			if d < self.events[i].getDelay():
				self.insert(i, e)
				return
		self.append(e)

	def _generateEID(self):
		"""
Internal function for generating EIDs.
		"""

		# To try and keep the EIDs low we use an algorithm
		# that allocates EID spaces of size 1024 and tries
		# to clame the lowest space available

		# Check if we have no more EIDs left
		if self.neid == self.eid_roof:
			eids = map(lambda e: e.getEID(), self.events)
			eids.sort()

			# Search for a 1024 EID gap
			eids.insert(0, -1)
			for i in range(len(eids) - 1):
				if eids[i + 1] - eids[i] >= 1024:
					self.neid = eids[i] + 1
					self.eid_roof = eids[i + 1]
					return self._generateEID()

			# If we were unable to find one create a new one at the end
			self.neid = eids[len(eids) - 1] + 1
			self.eid_roof = self.neid + 1024
			return self._generateEID()
		else:
			eid = self.neid
			self.neid += 1
			return eid

