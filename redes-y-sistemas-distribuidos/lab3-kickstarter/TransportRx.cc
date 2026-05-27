#ifndef TRANSPORTRX
#define TRANSPORTRX

#include <queue>
#include <omnetpp.h>

using namespace omnetpp;

enum PacketKind {
    DATA = 1,
    ACK = 2,
    WINDOW_UPDATE = 3
};

class TransportRx : public cSimpleModule {
    private:
        std::queue<cPacket*> rxBuffer;
        std::queue<cPacket*> feedbackQueue;
        int bufferSize;
        long packetsReceived;
        long packetsDelivered;
        cMessage *sendFeedbackEvent;
        cMessage *sendToAppEvent;
        cOutVector rxBufferOccupancyVector;

    public:
        TransportRx() : sendFeedbackEvent(nullptr), sendToAppEvent(nullptr) {}
        virtual ~TransportRx() {
            cancelAndDelete(sendFeedbackEvent);
            cancelAndDelete(sendToAppEvent);
            while (!rxBuffer.empty()) {
                delete rxBuffer.front();
                rxBuffer.pop();
            }
            while (!feedbackQueue.empty()) {
                delete feedbackQueue.front();
                feedbackQueue.pop();
            }
        }

    protected:
        virtual void initialize() override {
            bufferSize = par("bufferSize");
            packetsReceived = 0;
            packetsDelivered = 0;
            rxBufferOccupancyVector.setName("rxBufferOccupancy");
            sendFeedbackEvent = new cMessage("sendFeedbackEvent");
            sendToAppEvent = new cMessage("sendToAppEvent");
        }

        virtual void handleMessage(cMessage *msg) override {
            if (msg == sendFeedbackEvent) {
                trySendFeedback();
                return;
            }
            if (msg == sendToAppEvent) {
                tryDeliverToSink();
                return;
            }

            if (!msg->isSelfMessage()) {
                // paquete data de network
                cPacket *pkt = check_and_cast<cPacket*>(msg);
                packetsReceived++;

                // check si paquete viene marcado con ecn
                bool congestionMarked = (pkt->hasPar("ecn") && pkt->par("ecn").boolValue());
                int freeSlots = bufferSize - rxBuffer.size();

                if (freeSlots > 0) {
                    rxBuffer.push(pkt);
                    rxBufferOccupancyVector.record(rxBuffer.size());
                    
                    // enviar ack con rwnd y estado de congestion
                    sendFeedback(ACK, freeSlots, congestionMarked);

                    tryDeliverToSink();
                } else { // buffer lleno, descartamos
                    EV << "RX buffer full, dropping packet\n";
                    delete pkt;
                    //avisamos congestion
                    sendFeedback(WINDOW_UPDATE, 0, true);
                }
            }
            else {
                delete msg;
            }
        }

        void sendFeedback(int kind, int rwnd, bool congestionMarked) {
            cPacket *feedback = new cPacket("feedback");
            feedback->setByteLength(20);
            // setKind(2) para ack normal
            feedback->setKind(kind);
            feedback->addPar("rwnd") = rwnd;
            feedback->addPar("ecn") = congestionMarked;
            
            EV << "Queueing feedback: rwnd=" << rwnd << ", ecn=" << congestionMarked << "\n";
            feedbackQueue.push(feedback);
            trySendFeedback();
        }

        void trySendFeedback() {
            if (feedbackQueue.empty())
                return;

            cChannel *channel = gate("toOut$o")->findTransmissionChannel();
            if (channel && channel->isBusy()) {
                if (!sendFeedbackEvent->isScheduled()) {
                    scheduleAt(channel->getTransmissionFinishTime(), sendFeedbackEvent);
                }
                return;
            }

            cPacket *feedback = feedbackQueue.front();
            feedbackQueue.pop();
            EV << "Sending feedback: rwnd=" << feedback->par("rwnd").longValue() << ", ecn=" << feedback->par("ecn").boolValue() << "\n";
            send(feedback, "toOut$o");

            if (!feedbackQueue.empty()) {
                cChannel *nextChannel = gate("toOut$o")->findTransmissionChannel();
                if (nextChannel && !sendFeedbackEvent->isScheduled()) {
                    scheduleAt(nextChannel->getTransmissionFinishTime(), sendFeedbackEvent);
                }
            }
        }

        void tryDeliverToSink() {
            if (rxBuffer.empty())
                return;

            cChannel *channel = gate("toApp")->findTransmissionChannel();
            if (channel && channel->isBusy()) {
                if (!sendToAppEvent->isScheduled()) {
                    scheduleAt(channel->getTransmissionFinishTime(), sendToAppEvent);
                }
                return;
            }

            cPacket *pkt = rxBuffer.front();
            rxBuffer.pop();
            send(pkt, "toApp");
            packetsDelivered++;
            rxBufferOccupancyVector.record(rxBuffer.size());

            if (!rxBuffer.empty()) {
                cChannel *nextChannel = gate("toApp")->findTransmissionChannel();
                if (nextChannel && !sendToAppEvent->isScheduled()) {
                    scheduleAt(nextChannel->getTransmissionFinishTime(), sendToAppEvent);
                } else if (!sendToAppEvent->isScheduled()) {
                    scheduleAt(simTime() + SIMTIME_ZERO, sendToAppEvent);
                }
            }
        }

        virtual void finish() override {
            recordScalar("Total packets received", packetsReceived);
            recordScalar("Total packets delivered", packetsDelivered);
        }
};

Define_Module(TransportRx);
#endif